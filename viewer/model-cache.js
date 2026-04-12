const MODEL_CACHE_DB_NAME = '3dgs-viewer-model-cache';
const MODEL_CACHE_DB_VERSION = 1;
const MODEL_CACHE_STORE = 'models';

export function formatBytes(bytes) {
  if (!Number.isFinite(bytes) || bytes <= 0) {
    return '未知大小';
  }

  const units = ['B', 'KB', 'MB', 'GB'];
  let value = bytes;
  let unitIndex = 0;
  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024;
    unitIndex += 1;
  }
  return `${value.toFixed(unitIndex === 0 ? 0 : 1)} ${units[unitIndex]}`;
}

export function buildModelCacheKey(url, version, baseUrl = window.location.href) {
  const absoluteUrl = new URL(url, baseUrl).href;
  return {
    absoluteUrl,
    key: `${absoluteUrl}::${version ?? 'unversioned'}`,
  };
}

export function openModelCacheDb() {
  if (!window.indexedDB) {
    return Promise.resolve(null);
  }

  return new Promise((resolve, reject) => {
    const request = window.indexedDB.open(MODEL_CACHE_DB_NAME, MODEL_CACHE_DB_VERSION);
    request.onupgradeneeded = () => {
      const db = request.result;
      if (!db.objectStoreNames.contains(MODEL_CACHE_STORE)) {
        db.createObjectStore(MODEL_CACHE_STORE, { keyPath: 'key' });
      }
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
    request.onblocked = () => reject(new Error('IndexedDB upgrade blocked.'));
  });
}

export function readModelCacheEntry(db, key) {
  if (!db) {
    return Promise.resolve(null);
  }

  return new Promise((resolve, reject) => {
    const transaction = db.transaction(MODEL_CACHE_STORE, 'readonly');
    const request = transaction.objectStore(MODEL_CACHE_STORE).get(key);
    request.onsuccess = () => resolve(request.result ?? null);
    request.onerror = () => reject(request.error);
  });
}

export function writeModelCacheEntry(db, entry) {
  if (!db) {
    return Promise.resolve();
  }

  return new Promise((resolve, reject) => {
    const transaction = db.transaction(MODEL_CACHE_STORE, 'readwrite');
    transaction.objectStore(MODEL_CACHE_STORE).put(entry);
    transaction.oncomplete = () => resolve();
    transaction.onerror = () => reject(transaction.error);
  });
}

export function deleteOldModelCacheEntries(db, url, keepKey) {
  if (!db) {
    return Promise.resolve();
  }

  return new Promise((resolve, reject) => {
    const transaction = db.transaction(MODEL_CACHE_STORE, 'readwrite');
    const store = transaction.objectStore(MODEL_CACHE_STORE);
    const request = store.openCursor();
    request.onsuccess = () => {
      const cursor = request.result;
      if (!cursor) {
        return;
      }

      const value = cursor.value;
      if (value?.url === url && value.key !== keepKey) {
        cursor.delete();
      }
      cursor.continue();
    };
    transaction.oncomplete = () => resolve();
    transaction.onerror = () => reject(transaction.error);
  });
}

export function listModelCacheEntries() {
  return openModelCacheDb().then((db) => {
    if (!db) {
      return [];
    }

    return new Promise((resolve, reject) => {
      const entries = [];
      const transaction = db.transaction(MODEL_CACHE_STORE, 'readonly');
      const request = transaction.objectStore(MODEL_CACHE_STORE).openCursor();
      request.onsuccess = () => {
        const cursor = request.result;
        if (!cursor) {
          return;
        }

        const value = cursor.value;
        const size = value.size || value.blob?.size || 0;
        entries.push({
          key: value.key,
          url: value.url,
          version: value.version,
          contentType: value.contentType,
          size,
          sizeLabel: formatBytes(size),
          storedAt: value.storedAt,
        });
        cursor.continue();
      };
      transaction.oncomplete = () => resolve(entries.sort((a, b) => (b.storedAt || 0) - (a.storedAt || 0)));
      transaction.onerror = () => reject(transaction.error);
    });
  });
}

export function deleteModelCacheEntry(key) {
  return openModelCacheDb().then((db) => {
    if (!db) {
      return;
    }

    return new Promise((resolve, reject) => {
      const transaction = db.transaction(MODEL_CACHE_STORE, 'readwrite');
      transaction.objectStore(MODEL_CACHE_STORE).delete(key);
      transaction.oncomplete = () => resolve();
      transaction.onerror = () => reject(transaction.error);
    });
  });
}

export function clearModelCache() {
  return openModelCacheDb().then((db) => {
    if (!db) {
      return;
    }

    return new Promise((resolve, reject) => {
      const transaction = db.transaction(MODEL_CACHE_STORE, 'readwrite');
      transaction.objectStore(MODEL_CACHE_STORE).clear();
      transaction.oncomplete = () => resolve();
      transaction.onerror = () => reject(transaction.error);
    });
  });
}

export function buildCachedModelResponse(entry) {
  const headers = {
    'Content-Type': entry.contentType || 'application/octet-stream',
    'Content-Length': String(entry.size || entry.blob?.size || 0),
  };
  return new Response(entry.blob, { status: 200, headers });
}

export async function loadModelResponseWithCache(url, options = {}) {
  const {
    version = 'unversioned',
    onSource,
    onStatus,
  } = options;
  const { absoluteUrl, key } = buildModelCacheKey(url, version);
  let db = null;

  try {
    db = await openModelCacheDb();
    const cachedEntry = await readModelCacheEntry(db, key);
    if (cachedEntry?.blob) {
      onSource?.('cache');
      onStatus?.('正在读取本地模型缓存...', `${formatBytes(cachedEntry.blob.size)}，仍需解析并上传到 GPU。`);
      return buildCachedModelResponse(cachedEntry);
    }
  } catch (error) {
    console.warn('Model cache lookup failed. Falling back to network.', error);
  }

  onSource?.('network');
  onStatus?.('正在下载模型...', url);
  const response = await fetch(url);
  if (response.ok && db) {
    response.clone().blob()
      .then(async (blob) => {
        await deleteOldModelCacheEntries(db, absoluteUrl, key);
        await writeModelCacheEntry(db, {
          key,
          url: absoluteUrl,
          version,
          blob,
          contentType: response.headers.get('content-type') || 'application/octet-stream',
          size: blob.size,
          storedAt: Date.now(),
        });
      })
      .catch((error) => {
        console.warn('Model cache write failed.', error);
      });
  }

  return response;
}
