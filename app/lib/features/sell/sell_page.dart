// ignore_for_file: deprecated_member_use

import 'package:flutter/material.dart';

import '../../theme/app_colors.dart';
import '../../widgets/editorial_widgets.dart';

class SellPage extends StatelessWidget {
  const SellPage({
    super.key,
    required this.onGoHome,
    required this.onOpenSuccess,
    required this.onOpenReview,
  });

  final VoidCallback onGoHome;
  final VoidCallback onOpenSuccess;
  final VoidCallback onOpenReview;

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      bottom: false,
      child: ListView(
        padding: const EdgeInsets.fromLTRB(16, 16, 16, 128),
        children: [
          EditorialScreenHeader(
            title: 'Sell Item',
            onBack: onGoHome,
            trailing: Text(
              'Drafts',
              style: Theme.of(context).textTheme.labelLarge?.copyWith(color: AppColors.textMuted),
            ),
          ),
          const SizedBox(height: 16),
          const _PhotoGrid(),
          const SizedBox(height: 16),
          const _LabeledFieldCard(
            label: 'Product title',
            hint: 'Brand, model, key features',
          ),
          const SizedBox(height: 12),
          const _LabeledFieldCard(
            label: 'Description',
            hint: 'Describe condition, usage time, and reason for selling',
            maxLines: 5,
          ),
          const SizedBox(height: 12),
          const _TagRow(),
          const SizedBox(height: 16),
          const _ChoiceCard(),
          const SizedBox(height: 16),
          Text(
            'Pricing & logistics',
            style: Theme.of(context).textTheme.labelSmall?.copyWith(
                  color: AppColors.textMuted,
                  letterSpacing: 1.5,
                ),
          ),
          const SizedBox(height: 12),
          const _PriceRow(),
          const SizedBox(height: 12),
          const _ShippingPanel(),
          const SizedBox(height: 12),
          const _TrustNotice(),
          const SizedBox(height: 16),
          FilledButton(
            onPressed: onOpenSuccess,
            child: const Text('Post now'),
          ),
          const SizedBox(height: 10),
          TextButton(
            onPressed: onOpenReview,
            child: const Text('Preview review flow'),
          ),
        ],
      ),
    );
  }
}

class _PhotoGrid extends StatelessWidget {
  const _PhotoGrid();

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final mainWidth = (constraints.maxWidth - 12) / 2;

        return Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            SizedBox(
              width: mainWidth,
              child: EditorialImagePlaceholder(
                label: 'Main listing photo',
                subtitle: 'Front angle',
                badge: 'Hero',
                height: 244,
                borderRadius: 26,
                accentColor: AppColors.accent,
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                children: [
                  EditorialImagePlaceholder(
                    label: 'Detail shot',
                    subtitle: 'Texture & trim',
                    badge: 'Close-up',
                    height: 116,
                    borderRadius: 24,
                    accentColor: AppColors.surfaceRaised,
                  ),
                  const SizedBox(height: 12),
                  EditorialImagePlaceholder(
                    label: 'Video cover',
                    subtitle: '30 sec clip',
                    badge: 'Motion',
                    height: 116,
                    borderRadius: 24,
                    accentColor: AppColors.surfaceSoft,
                  ),
                ],
              ),
            ),
          ],
        );
      },
    );
  }
}

class _LabeledFieldCard extends StatelessWidget {
  const _LabeledFieldCard({required this.label, required this.hint, this.maxLines = 1});

  final String label;
  final String hint;
  final int maxLines;

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
          const SizedBox(height: 8),
          TextField(
            maxLines: maxLines,
            decoration: InputDecoration(
              hintText: hint,
              fillColor: Colors.transparent,
              filled: false,
              contentPadding: EdgeInsets.zero,
              hintStyle: Theme.of(context).textTheme.bodyLarge?.copyWith(
                    color: AppColors.textMuted.withOpacity(0.5),
                  ),
            ),
          ),
        ],
      ),
    );
  }
}

class _TagRow extends StatelessWidget {
  const _TagRow();

  @override
  Widget build(BuildContext context) {
    return const Wrap(
      spacing: 8,
      runSpacing: 8,
      children: [
        _InlineTag(label: '#Tech'),
        _InlineTag(label: '#Vintage'),
        _InlineTag(label: '+ Add tag'),
      ],
    );
  }
}

class _InlineTag extends StatelessWidget {
  const _InlineTag({required this.label});

  final String label;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 9),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(999),
      ),
      child: Text(
        label,
        style: Theme.of(context).textTheme.labelMedium?.copyWith(
              color: AppColors.text,
              fontWeight: FontWeight.w700,
            ),
      ),
    );
  }
}

class _ChoiceCard extends StatelessWidget {
  const _ChoiceCard();

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(24),
      ),
      child: Column(
        children: const [
          _ChoiceRow(icon: Icons.category_rounded, title: 'Category', value: 'Select category', topBorder: true),
          Divider(height: 1, color: AppColors.surfaceRaised),
          _ChoiceRow(icon: Icons.star_half_rounded, title: 'Condition', value: '99% new', topBorder: false),
        ],
      ),
    );
  }
}

class _ChoiceRow extends StatelessWidget {
  const _ChoiceRow({
    required this.icon,
    required this.title,
    required this.value,
    required this.topBorder,
  });

  final IconData icon;
  final String title;
  final String value;
  final bool topBorder;

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: topBorder ? AppColors.surfaceSoft : AppColors.surface,
        borderRadius: BorderRadius.vertical(
          top: topBorder ? const Radius.circular(24) : Radius.zero,
          bottom: topBorder ? Radius.zero : const Radius.circular(24),
        ),
      ),
      padding: const EdgeInsets.all(16),
      child: Row(
        children: [
          Icon(icon, color: AppColors.primary),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title.toUpperCase(),
                  style: Theme.of(context).textTheme.labelSmall?.copyWith(
                        color: AppColors.textMuted,
                        letterSpacing: 1.1,
                      ),
                ),
                const SizedBox(height: 4),
                Text(
                  value,
                  style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                        fontWeight: FontWeight.w700,
                      ),
                ),
              ],
            ),
          ),
          const Icon(Icons.chevron_right_rounded, color: AppColors.textMuted),
        ],
      ),
    );
  }
}

class _PriceRow extends StatelessWidget {
  const _PriceRow();

  @override
  Widget build(BuildContext context) {
    return Row(
      children: const [
        Expanded(
          child: _PriceCard(label: 'Selling price', prefix: '¥', valueHint: '0.00'),
        ),
        SizedBox(width: 12),
        Expanded(
          child: _PriceCard(label: 'Original price', prefix: '¥', valueHint: '0.00', muted: true),
        ),
      ],
    );
  }
}

class _PriceCard extends StatelessWidget {
  const _PriceCard({
    required this.label,
    required this.prefix,
    required this.valueHint,
    this.muted = false,
  });

  final String label;
  final String prefix;
  final String valueHint;
  final bool muted;

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
          const SizedBox(height: 8),
          Row(
            children: [
              Text(
                prefix,
                style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                      color: muted ? AppColors.textMuted.withOpacity(0.5) : AppColors.primary,
                    ),
              ),
              const SizedBox(width: 6),
              Expanded(
                child: TextField(
                  decoration: InputDecoration(
                    hintText: valueHint,
                    fillColor: Colors.transparent,
                    filled: false,
                    contentPadding: EdgeInsets.zero,
                    hintStyle: Theme.of(context).textTheme.headlineSmall?.copyWith(
                          color: AppColors.textMuted.withOpacity(0.45),
                          fontWeight: FontWeight.w800,
                        ),
                  ),
                  style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                        color: muted ? AppColors.textMuted : AppColors.text,
                        fontWeight: FontWeight.w800,
                      ),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _ShippingPanel extends StatelessWidget {
  const _ShippingPanel();

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(24),
      ),
      child: Row(
        children: [
          Container(
            width: 48,
            height: 48,
            decoration: const BoxDecoration(
              color: AppColors.accent,
              shape: BoxShape.circle,
            ),
            child: const Icon(Icons.local_shipping_rounded, color: AppColors.primary),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Shipping method', style: Theme.of(context).textTheme.titleSmall),
                const SizedBox(height: 4),
                Text('Free shipping or pick up', style: Theme.of(context).textTheme.bodySmall),
              ],
            ),
          ),
          Container(
            padding: const EdgeInsets.all(4),
            decoration: BoxDecoration(
              color: AppColors.surfaceSoft,
              borderRadius: BorderRadius.circular(999),
            ),
            child: Row(
              children: [
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
                  decoration: BoxDecoration(
                    color: AppColors.surface,
                    borderRadius: BorderRadius.circular(999),
                  ),
                  child: Text(
                    'Postage',
                    style: Theme.of(context).textTheme.labelSmall?.copyWith(color: AppColors.text),
                  ),
                ),
                const SizedBox(width: 4),
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 12),
                  child: Text(
                    'In person',
                    style: Theme.of(context).textTheme.labelSmall?.copyWith(color: AppColors.textMuted),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _TrustNotice extends StatelessWidget {
  const _TrustNotice();

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.mint.withOpacity(0.08),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: AppColors.mint.withOpacity(0.14)),
      ),
      child: Row(
        children: [
          Container(
            width: 38,
            height: 38,
            decoration: BoxDecoration(
              color: AppColors.mint.withOpacity(0.15),
              shape: BoxShape.circle,
            ),
            child: const Icon(Icons.verified_user_rounded, color: AppColors.mint, size: 20),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Text(
              'Your item will be protected by Amber Safeguard. Authentic transactions only.',
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    color: AppColors.mint,
                    height: 1.35,
                  ),
            ),
          ),
        ],
      ),
    );
  }
}
