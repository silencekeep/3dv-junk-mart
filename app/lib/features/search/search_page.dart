import 'package:flutter/material.dart';

import '../../theme/app_colors.dart';
import '../../widgets/editorial_widgets.dart';

class SearchPage extends StatelessWidget {
  const SearchPage({
    super.key,
    required this.onGoHome,
    required this.onOpenDetail,
  });

  final VoidCallback onGoHome;
  final VoidCallback onOpenDetail;

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      bottom: false,
      child: ListView(
        padding: const EdgeInsets.fromLTRB(16, 16, 16, 128),
        children: [
          Row(
            children: [
              EditorialRoundIconButton(
                icon: Icons.arrow_back_rounded,
                onTap: onGoHome,
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Container(
                  height: 52,
                  padding: const EdgeInsets.symmetric(horizontal: 16),
                  decoration: BoxDecoration(
                    color: AppColors.surface,
                    borderRadius: BorderRadius.circular(999),
                  ),
                  child: const Row(
                    children: [
                      Icon(Icons.search_rounded, color: AppColors.textMuted),
                      SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          'Leica',
                          style: TextStyle(
                            color: AppColors.text,
                            fontSize: 14,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(width: 12),
              const CircleAvatar(
                radius: 21,
                backgroundColor: AppColors.surface,
                child: Icon(Icons.tune_rounded, color: AppColors.text),
              ),
            ],
          ),
          const SizedBox(height: 14),
          SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            child: Row(
              children: const [
                _SearchFilterChip(label: 'General', selected: true),
                _SearchFilterChip(label: 'Credit'),
                _SearchFilterChip(label: 'Price'),
                _SearchFilterChip(label: 'Region'),
                _SearchFilterChip(label: 'Filters', icon: Icons.filter_list_rounded),
              ],
            ),
          ),
          const SizedBox(height: 16),
          const _SearchSummaryCard(),
          const SizedBox(height: 16),
          EditorialSectionHeader(
            title: 'Results',
            actionLabel: '24 items',
          ),
          const SizedBox(height: 12),
          LayoutBuilder(
            builder: (context, constraints) {
              final cardWidth = (constraints.maxWidth - 12) / 2;
              return Wrap(
                spacing: 12,
                runSpacing: 12,
                children: [
                  SizedBox(
                    width: cardWidth,
                    child: EditorialProductCard(
                      title: 'Leica M6 Classic Black Chrome w/ 35mm Summicron',
                      price: '¥28,500',
                      location: 'Beijing, China',
                      icon: Icons.camera_alt_rounded,
                      tag: 'Verified',
                      accentColor: AppColors.surfaceSoft,
                      onTap: onOpenDetail,
                    ),
                  ),
                  SizedBox(
                    width: cardWidth,
                    child: EditorialProductCard(
                      title: 'Sony A7M4 Body Only - Like New Condition',
                      price: '¥14,200',
                      location: 'Manhattan, NY',
                      icon: Icons.videocam_rounded,
                      tag: 'Seller',
                      accentColor: AppColors.surfaceRaised,
                      tall: true,
                      onTap: onOpenDetail,
                    ),
                  ),
                  SizedBox(
                    width: cardWidth,
                    child: EditorialProductCard(
                      title: 'Fujifilm X100V Silver Edition + Accessories',
                      price: '¥11,800',
                      location: 'Shanghai',
                      icon: Icons.photo_camera_rounded,
                      tag: 'Top pick',
                      accentColor: AppColors.mint,
                      tall: true,
                      onTap: onOpenDetail,
                    ),
                  ),
                  SizedBox(
                    width: cardWidth,
                    child: EditorialProductCard(
                      title: 'Leica Summilux-M 50mm f/1.4 ASPH Lens',
                      price: '¥22,600',
                      location: 'London, UK',
                      icon: Icons.lens_rounded,
                      tag: 'Trusted',
                      accentColor: AppColors.ocean,
                      onTap: onOpenDetail,
                    ),
                  ),
                ],
              );
            },
          ),
        ],
      ),
    );
  }
}

class _SearchFilterChip extends StatelessWidget {
  const _SearchFilterChip({required this.label, this.icon, this.selected = false});

  final String label;
  final IconData? icon;
  final bool selected;

  @override
  Widget build(BuildContext context) {
    final background = selected ? AppColors.accent : AppColors.surface;
    final foreground = selected ? AppColors.primary : AppColors.textMuted;

    return Padding(
      padding: const EdgeInsets.only(right: 10),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
        decoration: BoxDecoration(
          color: background,
          borderRadius: BorderRadius.circular(999),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            if (icon != null) ...[
              Icon(icon, size: 16, color: foreground),
              const SizedBox(width: 4),
            ],
            Text(
              label,
              style: Theme.of(context).textTheme.labelMedium?.copyWith(
                    color: foreground,
                    fontWeight: FontWeight.w700,
                  ),
            ),
          ],
        ),
      ),
    );
  }
}

class _SearchSummaryCard extends StatelessWidget {
  const _SearchSummaryCard();

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: AppColors.primary,
        borderRadius: BorderRadius.circular(28),
      ),
      child: Row(
        children: [
          SizedBox(
            width: 62,
            height: 62,
            child: EditorialImagePlaceholder(
              label: 'Leica',
              subtitle: 'Search',
              badge: 'Query',
              height: 62,
              borderRadius: 18,
              accentColor: AppColors.accent,
              compact: true,
            ),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Leica',
                  style: Theme.of(context).textTheme.titleLarge?.copyWith(color: Colors.white),
                ),
                const SizedBox(height: 4),
                Text(
                  'Curated camera listings, lenses, and accessories near you.',
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        color: Colors.white70,
                        height: 1.4,
                      ),
                ),
              ],
            ),
          ),
          const SizedBox(width: 10),
          const Icon(Icons.chevron_right_rounded, color: Colors.white70),
        ],
      ),
    );
  }
}
