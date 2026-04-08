// ignore_for_file: deprecated_member_use, use_null_aware_elements

import 'package:flutter/material.dart';

import '../theme/app_colors.dart';

class EditorialSectionHeader extends StatelessWidget {
  const EditorialSectionHeader({
    super.key,
    required this.title,
    required this.actionLabel,
    this.onActionTap,
  });

  final String title;
  final String actionLabel;
  final VoidCallback? onActionTap;

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Expanded(
          child: Text(
            title,
            style: Theme.of(context).textTheme.headlineSmall,
          ),
        ),
        if (onActionTap != null)
          InkWell(
            onTap: onActionTap,
            borderRadius: BorderRadius.circular(999),
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 2, vertical: 4),
              child: Row(
                children: [
                  Text(
                    actionLabel,
                    style: Theme.of(context).textTheme.labelSmall?.copyWith(
                          color: AppColors.textMuted,
                          letterSpacing: 1.2,
                        ),
                  ),
                  const SizedBox(width: 4),
                  const Icon(Icons.chevron_right_rounded, size: 18, color: AppColors.textMuted),
                ],
              ),
            ),
          )
        else
          Row(
            children: [
              Text(
                actionLabel,
                style: Theme.of(context).textTheme.labelSmall?.copyWith(
                      color: AppColors.textMuted,
                      letterSpacing: 1.2,
                    ),
              ),
              const SizedBox(width: 4),
              const Icon(Icons.keyboard_arrow_down_rounded, size: 18, color: AppColors.textMuted),
            ],
          ),
      ],
    );
  }
}

class EditorialPill extends StatelessWidget {
  const EditorialPill({
    super.key,
    required this.label,
    this.filled = false,
    this.backgroundColor,
    this.foregroundColor,
    this.icon,
  });

  final String label;
  final bool filled;
  final Color? backgroundColor;
  final Color? foregroundColor;
  final IconData? icon;

  @override
  Widget build(BuildContext context) {
    final background = backgroundColor ?? (filled ? AppColors.accent : AppColors.surfaceSoft);
    final foreground = foregroundColor ?? (filled ? AppColors.primary : AppColors.textMuted);

    return Container(
      padding: EdgeInsets.symmetric(horizontal: icon == null ? 12 : 10, vertical: 7),
      decoration: BoxDecoration(
        color: background,
        borderRadius: BorderRadius.circular(999),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (icon != null) ...[
            Icon(icon, size: 14, color: foreground),
            const SizedBox(width: 4),
          ],
          Text(
            label.toUpperCase(),
            style: Theme.of(context).textTheme.labelSmall?.copyWith(
                  color: foreground,
                  fontWeight: FontWeight.w800,
                  letterSpacing: 1.2,
                ),
          ),
        ],
      ),
    );
  }
}

class EditorialScreenHeader extends StatelessWidget {
  const EditorialScreenHeader({
    super.key,
    required this.title,
    required this.onBack,
    this.trailing,
  });

  final String title;
  final VoidCallback onBack;
  final Widget? trailing;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        EditorialRoundIconButton(
          icon: Icons.arrow_back_rounded,
          onTap: onBack,
        ),
        const SizedBox(width: 12),
        Expanded(
          child: Text(
            title,
            style: Theme.of(context).textTheme.headlineSmall,
          ),
        ),
        if (trailing != null) trailing!,
      ],
    );
  }
}

class EditorialRoundIconButton extends StatelessWidget {
  const EditorialRoundIconButton({super.key, required this.icon, required this.onTap});

  final IconData icon;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: AppColors.surface,
      shape: const CircleBorder(),
      child: InkWell(
        onTap: onTap,
        customBorder: const CircleBorder(),
        child: SizedBox(
          width: 44,
          height: 44,
          child: Icon(icon, color: AppColors.text),
        ),
      ),
    );
  }
}

class EditorialImagePlaceholder extends StatelessWidget {
  const EditorialImagePlaceholder({
    super.key,
    required this.label,
    this.subtitle,
    this.badge,
    this.height,
    this.aspectRatio = 1.1,
    this.accentColor = AppColors.accent,
    this.circular = false,
    this.borderRadius = 28,
    this.compact = false,
    this.icon = Icons.image_rounded,
  });

  final String label;
  final String? subtitle;
  final String? badge;
  final double? height;
  final double aspectRatio;
  final Color accentColor;
  final bool circular;
  final double borderRadius;
  final bool compact;
  final IconData icon;

  @override
  Widget build(BuildContext context) {
    final frame = Container(
      decoration: BoxDecoration(
        shape: circular ? BoxShape.circle : BoxShape.rectangle,
        borderRadius: circular ? null : BorderRadius.circular(borderRadius),
        gradient: LinearGradient(
          colors: [
            accentColor.withOpacity(0.96),
            Color.lerp(accentColor, Colors.white, 0.72) ?? Colors.white,
          ],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        border: Border.all(color: Colors.white.withOpacity(0.34)),
        boxShadow: const [
          BoxShadow(
            color: Color(0x10000000),
            blurRadius: 22,
            offset: Offset(0, 10),
          ),
        ],
      ),
      child: Stack(
        fit: StackFit.expand,
        children: [
          Positioned(
            left: -18,
            top: -16,
            child: Container(
              width: 92,
              height: 92,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: Colors.white.withOpacity(0.22),
              ),
            ),
          ),
          Positioned(
            right: -28,
            bottom: -28,
            child: Container(
              width: 128,
              height: 128,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: Colors.white.withOpacity(0.16),
              ),
            ),
          ),
          Positioned(
            left: 14,
            top: 14,
            child: EditorialPill(
              label: badge ?? 'Preview',
              backgroundColor: Colors.white.withOpacity(0.74),
              foregroundColor: AppColors.text,
            ),
          ),
          Center(
            child: Container(
              width: circular ? 56 : 90,
              height: circular ? 56 : 90,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: Colors.white.withOpacity(0.38),
              ),
              child: Icon(
                icon,
                size: circular ? 30 : 42,
                color: AppColors.primary,
              ),
            ),
          ),
          if (!compact && !circular)
            Positioned(
              left: 14,
              right: 14,
              bottom: 14,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(
                    label,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: Theme.of(context).textTheme.titleMedium?.copyWith(
                          color: AppColors.primary,
                        ),
                  ),
                  if (subtitle != null) ...[
                    const SizedBox(height: 4),
                    Text(
                      subtitle!,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: Theme.of(context).textTheme.bodySmall?.copyWith(
                            color: AppColors.primary.withOpacity(0.72),
                          ),
                    ),
                  ],
                ],
              ),
            ),
        ],
      ),
    );

    final wrapped = height != null
        ? SizedBox(height: height, child: frame)
        : AspectRatio(aspectRatio: aspectRatio, child: frame);

    if (circular) {
      return ClipOval(child: wrapped);
    }

    return ClipRRect(
      borderRadius: BorderRadius.circular(borderRadius),
      child: wrapped,
    );
  }
}

class EditorialProductCard extends StatelessWidget {
  const EditorialProductCard({
    super.key,
    required this.title,
    required this.price,
    required this.location,
    required this.onTap,
    required this.icon,
    this.tag = 'Curated',
    this.accentColor = AppColors.accent,
    this.tall = false,
  });

  final String title;
  final String price;
  final String location;
  final VoidCallback onTap;
  final IconData icon;
  final String tag;
  final Color accentColor;
  final bool tall;

  @override
  Widget build(BuildContext context) {
    final topHeight = tall ? 192.0 : 164.0;

    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(24),
        child: Container(
          decoration: BoxDecoration(
            color: AppColors.surface,
            borderRadius: BorderRadius.circular(24),
            boxShadow: const [
              BoxShadow(
                color: Color(0x14000000),
                blurRadius: 28,
                offset: Offset(0, 16),
              ),
            ],
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              SizedBox(
                height: topHeight,
                child: EditorialImagePlaceholder(
                  label: 'Photo preview',
                  subtitle: location,
                  badge: tag,
                  height: topHeight,
                  borderRadius: 24,
                  accentColor: accentColor,
                ),
              ),
              Padding(
                padding: const EdgeInsets.fromLTRB(14, 14, 14, 16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      title,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                            height: 1.35,
                            fontWeight: FontWeight.w600,
                          ),
                    ),
                    const SizedBox(height: 10),
                    Row(
                      children: [
                        Text(
                          price,
                          style: Theme.of(context).textTheme.titleLarge?.copyWith(
                                color: AppColors.coral,
                                fontWeight: FontWeight.w800,
                              ),
                        ),
                        const Spacer(),
                        const Icon(Icons.location_on_rounded, size: 14, color: AppColors.textMuted),
                        const SizedBox(width: 4),
                        Flexible(
                          child: Text(
                            location,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: Theme.of(context).textTheme.labelSmall,
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
      ),
    );
  }
}

class EditorialActionCard extends StatelessWidget {
  const EditorialActionCard({
    super.key,
    required this.title,
    required this.subtitle,
    required this.icon,
    required this.onTap,
  });

  final String title;
  final String subtitle;
  final IconData icon;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Material(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(22),
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(22),
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Row(
              children: [
                Container(
                  width: 50,
                  height: 50,
                  decoration: BoxDecoration(
                    color: AppColors.surfaceSoft,
                    borderRadius: BorderRadius.circular(18),
                  ),
                  child: Icon(icon, color: AppColors.primary),
                ),
                const SizedBox(width: 14),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        title,
                        style: Theme.of(context).textTheme.titleMedium,
                      ),
                      const SizedBox(height: 4),
                      Text(
                        subtitle,
                        style: Theme.of(context).textTheme.bodySmall,
                      ),
                    ],
                  ),
                ),
                const Icon(Icons.arrow_forward_ios_rounded, size: 16, color: AppColors.textMuted),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

