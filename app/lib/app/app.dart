import 'package:flutter/material.dart';

import '../features/auth/auth_pages.dart';
import '../features/shell/app_shell.dart';
import '../theme/app_theme.dart';

enum _AuthViewMode {
  login,
  register,
}

class JunkMartApp extends StatefulWidget {
  const JunkMartApp({super.key});

  @override
  State<JunkMartApp> createState() => _JunkMartAppState();
}

class _JunkMartAppState extends State<JunkMartApp> {
  bool _isAuthenticated = false;
  _AuthViewMode _authViewMode = _AuthViewMode.login;

  void _enterApp() {
    setState(() {
      _isAuthenticated = true;
    });
  }

  void _signOut() {
    setState(() {
      _isAuthenticated = false;
      _authViewMode = _AuthViewMode.login;
    });
  }

  void _showLogin() {
    setState(() {
      _authViewMode = _AuthViewMode.login;
    });
  }

  void _showRegister() {
    setState(() {
      _authViewMode = _AuthViewMode.register;
    });
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      title: 'Junk Mart',
      theme: buildAppTheme(),
      home: _isAuthenticated
          ? AppShell(onSignOut: _signOut)
          : _authViewMode == _AuthViewMode.login
              ? AuthLoginPage(
                  onSubmit: _enterApp,
                  onSwitchToRegister: _showRegister,
                  onContinueAsGuest: _enterApp,
                )
              : AuthRegisterPage(
                  onSubmit: _enterApp,
                  onSwitchToLogin: _showLogin,
                ),
    );
  }
}
