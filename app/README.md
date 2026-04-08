# app

Flutter frontend for the Junk Mart demo.

## Run
1. `flutter pub get`
2. `flutter run`

The app opens on the auth demo gate first. Use sign in or continue as guest to enter the marketplace shell.

Use `flutter run -d android` for a connected phone, or `flutter run -d windows` / `flutter run -d chrome` for desktop and web targets.

## Build
- `flutter build apk --debug`

## Notes
- The app is split into `lib/app`, `lib/features`, `lib/navigation`, `lib/theme`, and `lib/widgets`.
- Demo navigation is wired so the main tabs and detail flows are reachable after a fresh pull.
