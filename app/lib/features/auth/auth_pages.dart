// ignore_for_file: deprecated_member_use

import 'package:flutter/material.dart';

import '../../theme/app_colors.dart';
import '../../widgets/editorial_widgets.dart';

class AuthLoginPage extends StatefulWidget {
  const AuthLoginPage({
    super.key,
    required this.onSubmit,
    required this.onSwitchToRegister,
    required this.onContinueAsGuest,
  });

  final VoidCallback onSubmit;
  final VoidCallback onSwitchToRegister;
  final VoidCallback onContinueAsGuest;

  @override
  State<AuthLoginPage> createState() => _AuthLoginPageState();
}

class _AuthLoginPageState extends State<AuthLoginPage> {
  bool _rememberDevice = true;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      body: SafeArea(
        bottom: false,
        child: ListView(
          key: const PageStorageKey<String>('auth-login-list'),
          padding: const EdgeInsets.fromLTRB(16, 16, 16, 24),
          children: [
            Row(
              children: [
                const CircleAvatar(
                  radius: 22,
                  backgroundColor: AppColors.surface,
                  child: Icon(Icons.shopping_bag_rounded, color: AppColors.primary),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('Junk Mart', style: Theme.of(context).textTheme.titleLarge),
                      const SizedBox(height: 2),
                      Text('Secure access for buyers and sellers', style: Theme.of(context).textTheme.bodySmall),
                    ],
                  ),
                ),
                EditorialPill(
                  label: 'Auth',
                  backgroundColor: AppColors.accent,
                  foregroundColor: AppColors.primary,
                ),
              ],
            ),
            const SizedBox(height: 18),
            EditorialImagePlaceholder(
              label: 'Junk Mart access',
              subtitle: 'Sign in to continue your demo journey.',
              badge: 'Secure login',
              height: 204,
              borderRadius: 30,
              accentColor: AppColors.accent,
            ),
            const SizedBox(height: 16),
            Text('Welcome back', style: Theme.of(context).textTheme.displaySmall),
            const SizedBox(height: 8),
            Text(
              'Use the phone or email address you registered with. Sign in to manage orders, chats, and listings.',
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(height: 1.45),
            ),
            const SizedBox(height: 18),
            const _AuthInputField(
              label: 'Phone or email',
              hintText: 'you@example.com or 138 0000 0000',
              icon: Icons.person_outline_rounded,
            ),
            const SizedBox(height: 12),
            const _AuthInputField(
              label: 'Password',
              hintText: 'Enter your password',
              icon: Icons.lock_outline_rounded,
              obscureText: true,
            ),
            const SizedBox(height: 8),
            CheckboxListTile(
              contentPadding: EdgeInsets.zero,
              value: _rememberDevice,
              onChanged: (value) {
                setState(() {
                  _rememberDevice = value ?? false;
                });
              },
              title: const Text('Remember this device'),
              subtitle: Text('Keeps the demo session active until you sign out.', style: Theme.of(context).textTheme.bodySmall),
              controlAffinity: ListTileControlAffinity.leading,
              activeColor: AppColors.accentDeep,
            ),
            const SizedBox(height: 4),
            FilledButton(
              onPressed: widget.onSubmit,
              child: const Text('Sign in'),
            ),
            const SizedBox(height: 10),
            OutlinedButton(
              onPressed: widget.onContinueAsGuest,
              child: const Text('Continue as guest'),
            ),
            const SizedBox(height: 14),
            Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Text('New here?', style: Theme.of(context).textTheme.bodySmall),
                TextButton(
                  onPressed: widget.onSwitchToRegister,
                  child: const Text('Create account'),
                ),
              ],
            ),
            const SizedBox(height: 8),
            const _AuthInfoCard(
              title: 'What happens after sign in',
              body: 'Your profile, messages, orders, and sell drafts all use the same user identity.',
              icon: Icons.shield_outlined,
            ),
          ],
        ),
      ),
    );
  }
}

class AuthRegisterPage extends StatefulWidget {
  const AuthRegisterPage({
    super.key,
    required this.onSubmit,
    required this.onSwitchToLogin,
  });

  final VoidCallback onSubmit;
  final VoidCallback onSwitchToLogin;

  @override
  State<AuthRegisterPage> createState() => _AuthRegisterPageState();
}

class _AuthRegisterPageState extends State<AuthRegisterPage> {
  bool _acceptedTerms = true;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      body: SafeArea(
        bottom: false,
        child: ListView(
          key: const PageStorageKey<String>('auth-register-list'),
          padding: const EdgeInsets.fromLTRB(16, 16, 16, 24),
          children: [
            Row(
              children: [
                EditorialRoundIconButton(
                  icon: Icons.arrow_back_rounded,
                  onTap: widget.onSwitchToLogin,
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('Create your account', style: Theme.of(context).textTheme.titleLarge),
                      const SizedBox(height: 2),
                      Text('Join to post items, track orders, and message sellers.', style: Theme.of(context).textTheme.bodySmall),
                    ],
                  ),
                ),
                EditorialPill(
                  label: 'Join',
                  backgroundColor: AppColors.surfaceSoft,
                  foregroundColor: AppColors.text,
                ),
              ],
            ),
            const SizedBox(height: 18),
            EditorialImagePlaceholder(
              label: 'Open a new account',
              subtitle: 'Your profile and listings are created together.',
              badge: 'Register',
              height: 204,
              borderRadius: 30,
              accentColor: AppColors.surfaceRaised,
            ),
            const SizedBox(height: 16),
            Text('Build your profile', style: Theme.of(context).textTheme.displaySmall),
            const SizedBox(height: 8),
            Text(
              'Create a seller-ready profile once. The backend should issue the user record, profile snapshot, and login session together.',
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(height: 1.45),
            ),
            const SizedBox(height: 18),
            const _AuthInputField(
              label: 'Display name',
              hintText: 'How your name appears in the app',
              icon: Icons.badge_outlined,
            ),
            const SizedBox(height: 12),
            const _AuthInputField(
              label: 'Phone or email',
              hintText: 'Primary sign-in identifier',
              icon: Icons.alternate_email_rounded,
            ),
            const SizedBox(height: 12),
            const _AuthInputField(
              label: 'Password',
              hintText: 'Create a password',
              icon: Icons.lock_outline_rounded,
              obscureText: true,
            ),
            const SizedBox(height: 12),
            const _AuthInputField(
              label: 'Confirm password',
              hintText: 'Repeat your password',
              icon: Icons.lock_reset_outlined,
              obscureText: true,
            ),
            const SizedBox(height: 8),
            CheckboxListTile(
              contentPadding: EdgeInsets.zero,
              value: _acceptedTerms,
              onChanged: (value) {
                setState(() {
                  _acceptedTerms = value ?? false;
                });
              },
              title: const Text('I agree to the terms and privacy policy'),
              subtitle: Text('The consent record is stored alongside the account.', style: Theme.of(context).textTheme.bodySmall),
              controlAffinity: ListTileControlAffinity.leading,
              activeColor: AppColors.accentDeep,
            ),
            const SizedBox(height: 4),
            FilledButton(
              onPressed: _acceptedTerms ? widget.onSubmit : null,
              child: const Text('Create account'),
            ),
            const SizedBox(height: 10),
            OutlinedButton(
              onPressed: widget.onSwitchToLogin,
              child: const Text('Back to sign in'),
            ),
            const SizedBox(height: 14),
            const _AuthInfoCard(
              title: 'Database closure',
              body: 'Registration should create the user row, profile row, consent row, and session row in one logical flow.',
              icon: Icons.data_object_rounded,
            ),
          ],
        ),
      ),
    );
  }
}

class _AuthInputField extends StatelessWidget {
  const _AuthInputField({
    required this.label,
    required this.hintText,
    required this.icon,
    this.obscureText = false,
  });

  final String label;
  final String hintText;
  final IconData icon;
  final bool obscureText;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(24),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            label.toUpperCase(),
            style: Theme.of(context).textTheme.labelSmall?.copyWith(
                  color: AppColors.textMuted,
                  letterSpacing: 1.1,
                ),
          ),
          const SizedBox(height: 10),
          TextField(
            obscureText: obscureText,
            decoration: InputDecoration(
              prefixIcon: Icon(icon, size: 18, color: AppColors.textMuted),
              hintText: hintText,
              fillColor: Colors.transparent,
              filled: false,
              contentPadding: EdgeInsets.zero,
              border: InputBorder.none,
              enabledBorder: InputBorder.none,
              focusedBorder: InputBorder.none,
              hintStyle: Theme.of(context).textTheme.bodyMedium?.copyWith(
                  color: AppColors.textMuted.withValues(alpha: 0.5),
                  ),
            ),
          ),
        ],
      ),
    );
  }
}

class _AuthInfoCard extends StatelessWidget {
  const _AuthInfoCard({required this.title, required this.body, required this.icon});

  final String title;
  final String body;
  final IconData icon;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.surfaceSoft,
        borderRadius: BorderRadius.circular(24),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 42,
            height: 42,
            decoration: const BoxDecoration(
              color: AppColors.surface,
              shape: BoxShape.circle,
            ),
            child: Icon(icon, color: AppColors.primary, size: 20),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(title, style: Theme.of(context).textTheme.titleSmall),
                const SizedBox(height: 4),
                Text(body, style: Theme.of(context).textTheme.bodySmall?.copyWith(height: 1.35)),
              ],
            ),
          ),
        ],
      ),
    );
  }
}