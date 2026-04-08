# 3dv-junk-mart

This repository contains a Flutter frontend in `app/` and a FastAPI backend placeholder in `backend/`.

## Layout
- `app/` - Flutter frontend application
- `backend/` - FastAPI backend placeholder
- `API_PROTO.md` - Frontend/backend communication contract
- `DATABASE_PROTO.md` - Backend database prototype

## Run the Flutter app
1. `cd app`
2. `flutter pub get`
3. `flutter run`

The app opens on the login/register demo gate first. Use sign in or continue as guest to reach the marketplace shell.

For Android specifically, use `flutter run -d android` or build a debug APK with `flutter build apk --debug`.

## Backend baseline
- Python version: 3.10.*
- Backend dependency file: `backend/requirements.txt`
- Backend documentation: `backend/README.md`

## Implementation docs
- API contract: `API_PROTO.md`
- Database prototype: `DATABASE_PROTO.md`

## Notes
- Keep Android SDK or desktop/web targets installed locally as needed.
- The repo is structured so a fresh pull can restore dependencies and run the frontend without extra code changes.

## TODO
- 3DGSEngine: JerryChen-USTB
- API Backend & Database : why912
- App frontend : JeoLi
