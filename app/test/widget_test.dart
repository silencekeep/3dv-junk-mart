import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:app/app/app.dart';

void main() {
  testWidgets('auth settings and shell flow work', (WidgetTester tester) async {
    await tester.pumpWidget(const JunkMartApp());

    expect(find.text('Welcome back'), findsOneWidget);

    await tester.drag(
      find.byKey(const PageStorageKey<String>('auth-login-list')),
      const Offset(0, -500),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.text('Create account'));
    await tester.pumpAndSettle();

    expect(find.text('Create your account'), findsOneWidget);

    await tester.tap(find.byIcon(Icons.arrow_back_rounded));
    await tester.pumpAndSettle();

    await tester.tap(find.text('Sign in'));
    await tester.pumpAndSettle();

    expect(find.text('Search curated items...'), findsOneWidget);
    expect(find.text('Home'), findsOneWidget);

    await tester.tap(find.text('Profile').first);
    await tester.pumpAndSettle();

    await tester.tap(find.byIcon(Icons.settings_rounded));
    await tester.pumpAndSettle();

    expect(find.text('Profile settings'), findsOneWidget);
    expect(find.text('NICKNAME'), findsOneWidget);
    expect(find.text('BIRTH DATE'), findsOneWidget);
    expect(find.text('AGE'), findsOneWidget);
    await tester.drag(
      find.byKey(const PageStorageKey<String>('profile-settings-list')),
      const Offset(0, -450),
    );
    await tester.pumpAndSettle();
    expect(find.text('Profile visibility'), findsOneWidget);

    await tester.drag(
      find.byKey(const PageStorageKey<String>('profile-settings-list')),
      const Offset(0, 1000),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.byIcon(Icons.arrow_back_rounded));
    await tester.pumpAndSettle();
    expect(find.text('Profile'), findsWidgets);
  });
}
