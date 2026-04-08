import 'package:flutter/material.dart';

import '../../theme/app_colors.dart';
import '../../widgets/editorial_widgets.dart';

class ProfileSettingsPage extends StatefulWidget {
  const ProfileSettingsPage({super.key, required this.onSave});

  final VoidCallback onSave;

  @override
  State<ProfileSettingsPage> createState() => _ProfileSettingsPageState();
}

class _ProfileSettingsPageState extends State<ProfileSettingsPage> {
  final DateTime _birthDate = DateTime(1998, 4, 8);
  String _visibility = 'public';

  int get _ageYears => _calculateAgeYears(_birthDate);

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      body: SafeArea(
        child: ListView(
          key: const PageStorageKey<String>('profile-settings-list'),
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 128),
          children: [
            EditorialScreenHeader(
              title: 'Profile settings',
              onBack: () => Navigator.pop(context),
              trailing: EditorialPill(
                label: 'Personal info',
                backgroundColor: AppColors.surfaceSoft,
                foregroundColor: AppColors.text,
              ),
            ),
            const SizedBox(height: 16),
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: AppColors.surface,
                borderRadius: BorderRadius.circular(28),
                boxShadow: const [
                  BoxShadow(color: Color(0x10000000), blurRadius: 24, offset: Offset(0, 10)),
                ],
              ),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.center,
                children: [
                  SizedBox(
                    width: 104,
                    height: 104,
                    child: EditorialImagePlaceholder(
                      label: 'Avatar',
                      subtitle: 'Change photo',
                      badge: 'Profile',
                      height: 104,
                      circular: true,
                      borderRadius: 999,
                      accentColor: AppColors.accent,
                    ),
                  ),
                  const SizedBox(width: 14),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text('Avatar and nickname', style: Theme.of(context).textTheme.headlineSmall),
                        const SizedBox(height: 6),
                        Text(
                          'The backend should persist avatar, nickname, and other profile fields together so the app can restore the same identity everywhere.',
                          style: Theme.of(context).textTheme.bodySmall?.copyWith(height: 1.45),
                        ),
                        const SizedBox(height: 12),
                        Row(
                          children: [
                            Expanded(
                              child: OutlinedButton(
                                onPressed: () {},
                                child: const Text('Change photo'),
                              ),
                            ),
                            const SizedBox(width: 10),
                            Expanded(
                              child: TextButton(
                                onPressed: () {},
                                child: const Text('Remove'),
                              ),
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 16),
            _ProfileFieldCard(
              label: 'Nickname',
              hint: 'Julian Thorne',
              icon: Icons.badge_outlined,
            ),
            const SizedBox(height: 12),
            _ProfileFieldCard(
              label: 'Birth date',
              hint: '1998-04-08',
              icon: Icons.cake_outlined,
            ),
            const SizedBox(height: 12),
            _ProfileFieldCard(
              label: 'Age',
              hint: '$_ageYears',
              icon: Icons.numbers_rounded,
              readOnly: true,
              helperText: 'Age is derived from the birth date stored in the database.',
            ),
            const SizedBox(height: 12),
            _ProfileFieldCard(
              label: 'Location',
              hint: 'Brooklyn, NY',
              icon: Icons.location_on_rounded,
            ),
            const SizedBox(height: 12),
            _ProfileFieldCard(
              label: 'Bio',
              hint: 'Collector, seller, and weekend curator',
              icon: Icons.text_fields_rounded,
              maxLines: 4,
            ),
            const SizedBox(height: 16),
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: AppColors.surface,
                borderRadius: BorderRadius.circular(24),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Profile visibility',
                    style: Theme.of(context).textTheme.labelSmall?.copyWith(
                          color: AppColors.textMuted,
                          letterSpacing: 1.1,
                        ),
                  ),
                  const SizedBox(height: 10),
                  Wrap(
                    spacing: 8,
                    runSpacing: 8,
                    children: [
                      _VisibilityChip(
                        label: 'Public',
                        selected: _visibility == 'public',
                        onSelected: () => setState(() => _visibility = 'public'),
                      ),
                      _VisibilityChip(
                        label: 'Friends',
                        selected: _visibility == 'friends',
                        onSelected: () => setState(() => _visibility = 'friends'),
                      ),
                      _VisibilityChip(
                        label: 'Private',
                        selected: _visibility == 'private',
                        onSelected: () => setState(() => _visibility = 'private'),
                      ),
                    ],
                  ),
                  const SizedBox(height: 8),
                  Text(
                    'Controls who can see your profile summary and listings.',
                    style: Theme.of(context).textTheme.bodySmall?.copyWith(height: 1.4),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 16),
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: AppColors.surfaceSoft,
                borderRadius: BorderRadius.circular(24),
              ),
              child: Row(
                children: [
                  Container(
                    width: 42,
                    height: 42,
                    decoration: const BoxDecoration(
                      color: AppColors.surface,
                      shape: BoxShape.circle,
                    ),
                    child: const Icon(Icons.shield_outlined, color: AppColors.primary, size: 20),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Text(
                      'Profile changes should update the user profile row and keep the auth session snapshot consistent.',
                      style: Theme.of(context).textTheme.bodySmall?.copyWith(height: 1.4),
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 16),
            FilledButton(
              onPressed: widget.onSave,
              child: const Text('Save changes'),
            ),
          ],
        ),
      ),
    );
  }

  int _calculateAgeYears(DateTime birthDate) {
    final now = DateTime.now();
    var age = now.year - birthDate.year;
    final hadBirthdayThisYear = now.month > birthDate.month || (now.month == birthDate.month && now.day >= birthDate.day);
    if (!hadBirthdayThisYear) {
      age -= 1;
    }
    return age;
  }
}

class _ProfileFieldCard extends StatelessWidget {
  const _ProfileFieldCard({
    required this.label,
    required this.hint,
    required this.icon,
    this.maxLines = 1,
    this.readOnly = false,
    this.helperText,
  });

  final String label;
  final String hint;
  final IconData icon;
  final int maxLines;
  final bool readOnly;
  final String? helperText;

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
          TextFormField(
            readOnly: readOnly,
            maxLines: maxLines,
            initialValue: hint,
            decoration: InputDecoration(
              prefixIcon: Icon(icon, size: 18, color: AppColors.textMuted),
              hintText: hint,
              fillColor: Colors.transparent,
              filled: false,
              contentPadding: EdgeInsets.zero,
              border: InputBorder.none,
              enabledBorder: InputBorder.none,
              focusedBorder: InputBorder.none,
              hintStyle: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    color: AppColors.textMuted.withValues(alpha: 0.52),
                  ),
            ),
          ),
          if (helperText != null) ...[
            const SizedBox(height: 8),
            Text(helperText!, style: Theme.of(context).textTheme.bodySmall),
          ],
        ],
      ),
    );
  }
}

class _VisibilityChip extends StatelessWidget {
  const _VisibilityChip({required this.label, required this.selected, required this.onSelected});

  final String label;
  final bool selected;
  final VoidCallback onSelected;

  @override
  Widget build(BuildContext context) {
    return ChoiceChip(
      label: Text(label),
      selected: selected,
      onSelected: (_) => onSelected(),
      labelStyle: Theme.of(context).textTheme.labelMedium?.copyWith(
            color: selected ? AppColors.primary : AppColors.textMuted,
            fontWeight: FontWeight.w700,
          ),
    );
  }
}