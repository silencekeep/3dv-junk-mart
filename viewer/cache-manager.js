import {
  clearModelCache,
  deleteModelCacheEntry,
  formatBytes,
  listModelCacheEntries,
} from './model-cache.js?v=20260408_43';

const summaryLabel = document.getElementById('cache-summary');
const cacheList = document.getElementById('cache-list');
const refreshButton = document.getElementById('refresh-cache');
const clearButton = document.getElementById('clear-cache');

function formatStoredAt(timestamp) {
  if (!Number.isFinite(timestamp)) {
    return '未知时间';
  }
  return new Date(timestamp).toLocaleString();
}

function setBusy(busy) {
  refreshButton.disabled = busy;
  clearButton.disabled = busy;
}

function renderEntries(entries) {
  const totalSize = entries.reduce((sum, entry) => sum + (entry.size || 0), 0);
  summaryLabel.textContent = `${entries.length} 个模型缓存，共 ${formatBytes(totalSize)}`;

  cacheList.replaceChildren();
  if (entries.length === 0) {
    const empty = document.createElement('li');
    empty.className = 'cache-empty';
    empty.textContent = '暂无本地模型缓存';
    cacheList.appendChild(empty);
    return;
  }

  for (const entry of entries) {
    const item = document.createElement('li');
    item.className = 'cache-item';

    const main = document.createElement('div');
    main.className = 'cache-item-main';

    const title = document.createElement('strong');
    title.textContent = entry.url ?? entry.key;

    const meta = document.createElement('span');
    meta.textContent = `${entry.sizeLabel} · ${formatStoredAt(entry.storedAt)}`;

    const version = document.createElement('small');
    version.textContent = `version: ${entry.version ?? 'unversioned'}`;

    main.append(title, meta, version);

    const deleteButton = document.createElement('button');
    deleteButton.type = 'button';
    deleteButton.className = 'danger';
    deleteButton.textContent = '删除';
    deleteButton.addEventListener('click', async () => {
      deleteButton.disabled = true;
      await deleteModelCacheEntry(entry.key);
      await refreshCacheList();
    });

    item.append(main, deleteButton);
    cacheList.appendChild(item);
  }
}

export async function refreshCacheList() {
  setBusy(true);
  try {
    renderEntries(await listModelCacheEntries());
  } catch (error) {
    console.error(error);
    summaryLabel.textContent = '读取缓存失败，请查看 WebView 控制台';
    cacheList.replaceChildren();
  } finally {
    setBusy(false);
  }
}

async function clearAllCache() {
  if (!window.confirm('确定删除所有本地模型缓存吗？下次查看模型会重新下载。')) {
    return;
  }

  setBusy(true);
  try {
    await clearModelCache();
    await refreshCacheList();
  } finally {
    setBusy(false);
  }
}

window.viewerModelCache = {
  list: listModelCacheEntries,
  delete: deleteModelCacheEntry,
  clear: clearModelCache,
  refresh: refreshCacheList,
};

refreshButton.addEventListener('click', () => refreshCacheList());
clearButton.addEventListener('click', () => clearAllCache());

refreshCacheList();
