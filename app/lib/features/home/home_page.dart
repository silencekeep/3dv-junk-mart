// ignore_for_file: deprecated_member_use

import 'package:flutter/material.dart';

import '../../theme/app_colors.dart';
import '../../widgets/editorial_widgets.dart';

class HomePage extends StatelessWidget {
  const HomePage({
    super.key,
    required this.onGoSearch,
    required this.onOpenDetail,
    required this.onOpenOrder,
    required this.onOpenChat,
    required this.onOpenReview,
    required this.onOpenSuccess,
  });

  final VoidCallback onGoSearch;
  final VoidCallback onOpenDetail;
  final VoidCallback onOpenOrder;
  final VoidCallback onOpenChat;
  final VoidCallback onOpenReview;
  final VoidCallback onOpenSuccess;

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      bottom: false,
      child: ListView(
        padding: const EdgeInsets.fromLTRB(16, 16, 16, 128),
        children: [
          _HomeHeader(onGoSearch: onGoSearch),
          const SizedBox(height: 16),
          const _HeroBanner(),
          const SizedBox(height: 18),
          EditorialSectionHeader(
            title: 'Categories',
            actionLabel: 'Browse all',
            onActionTap: () {},
          ),
          const SizedBox(height: 12),
          const _CategoryGrid(),
          const SizedBox(height: 18),
          EditorialSectionHeader(
            title: 'Curated picks',
            actionLabel: 'Today',
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
                      title: 'Custom 65% Mechanical Keyboard - Cream Switches',
                      price: '\$185',
                      location: 'Austin, TX',
                      icon: Icons.keyboard_rounded,
                      tag: 'Verified',
                      accentColor: AppColors.accent,
                      onTap: onOpenDetail,
                    ),
                  ),
                  SizedBox(
                    width: cardWidth,
                    child: EditorialProductCard(
                      title: 'Studio Grade Headphones - Like New',
                      price: '\$340',
                      location: 'Brooklyn, NY',
                      icon: Icons.headphones_rounded,
                      tag: 'Nearby',
                      accentColor: AppColors.surfaceRaised,
                      tall: true,
                      onTap: onOpenDetail,
                    ),
                  ),
                  SizedBox(
                    width: cardWidth,
                    child: EditorialProductCard(
                      title: 'Classic Red Runners - Size 10',
                      price: '\$95',
                      location: 'Tokyo',
                      icon: Icons.directions_run_rounded,
                      tag: 'Hot',
                      accentColor: AppColors.surfaceSoft,
                      onTap: onOpenDetail,
                    ),
                  ),
                  SizedBox(
                    width: cardWidth,
                    child: EditorialProductCard(
                      title: 'First Edition Collection - 3 Rare Volumes',
                      price: '\$1,200',
                      location: 'London',
                      icon: Icons.menu_book_rounded,
                      tag: 'Curated',
                      accentColor: AppColors.ocean,
                      tall: true,
                      onTap: onOpenDetail,
                    ),
                  ),
                ],
              );
            },
          ),
          const SizedBox(height: 20),
          EditorialSectionHeader(
            title: 'Quick actions',
            actionLabel: 'Jump in',
          ),
          const SizedBox(height: 12),
          EditorialActionCard(
            title: 'Product detail',
            subtitle: 'Open the editorial listing screen',
            icon: Icons.photo_size_select_actual_rounded,
            onTap: onOpenDetail,
          ),
          EditorialActionCard(
            title: 'Order detail',
            subtitle: 'Shipping and pricing breakdown',
            icon: Icons.local_shipping_rounded,
            onTap: onOpenOrder,
          ),
          EditorialActionCard(
            title: 'Chat thread',
            subtitle: 'Conversation and quick reply dock',
            icon: Icons.chat_bubble_outline_rounded,
            onTap: onOpenChat,
          ),
          EditorialActionCard(
            title: 'Review flow',
            subtitle: 'Rating, tags, and media upload',
            icon: Icons.rate_review_rounded,
            onTap: onOpenReview,
          ),
          EditorialActionCard(
            title: 'Success flow',
            subtitle: 'Wallet success and recommendations',
            icon: Icons.verified_rounded,
            onTap: onOpenSuccess,
          ),
        ],
      ),
    );
  }
}

class _HomeHeader extends StatelessWidget {
  const _HomeHeader({required this.onGoSearch});

  final VoidCallback onGoSearch;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        const CircleAvatar(
          radius: 21,
          backgroundColor: AppColors.surface,
          child: Icon(Icons.person_rounded, color: AppColors.textMuted),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: GestureDetector(
            onTap: onGoSearch,
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
                      'Search curated items...',
                      style: TextStyle(
                        color: AppColors.textMuted,
                        fontSize: 13,
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                  ),
                  Icon(Icons.center_focus_weak_rounded, color: AppColors.textMuted),
                ],
              ),
            ),
          ),
        ),
        const SizedBox(width: 12),
        const CircleAvatar(
          radius: 21,
          backgroundColor: AppColors.surface,
          child: Icon(Icons.notifications_none_rounded, color: AppColors.textMuted),
        ),
      ],
    );
  }
}

class _HeroBanner extends StatelessWidget {
  const _HeroBanner();

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 228,
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          colors: [Color(0xFFFFD83D), Color(0xFFFFF1A6)],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(32),
        boxShadow: const [
          BoxShadow(
            color: Color(0x1AFFD83D),
            blurRadius: 28,
            offset: Offset(0, 14),
          ),
        ],
      ),
      child: Stack(
        children: [
          Positioned(
            right: -36,
            bottom: -22,
            child: Container(
              width: 180,
              height: 180,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: Colors.white.withOpacity(0.18),
              ),
            ),
          ),
          Positioned(
            left: 18,
            top: 18,
            child: EditorialPill(
              label: 'Limited drop',
              backgroundColor: Colors.white.withOpacity(0.42),
              foregroundColor: AppColors.primary,
            ),
          ),
          Positioned(
            left: 18,
            top: 64,
            right: 140,
            child: Text(
              'Vintage\nreborn.',
              style: Theme.of(context).textTheme.displaySmall?.copyWith(
                    color: AppColors.primary,
                    height: 0.94,
                  ),
            ),
          ),
          Positioned(
            left: 18,
            bottom: 20,
            right: 140,
            child: Text(
              'Discover curated 90s tech, apparel, and objects from verified collectors.',
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    color: AppColors.primary.withOpacity(0.82),
                    height: 1.45,
                  ),
            ),
          ),
          Positioned(
            right: 18,
            top: 18,
            bottom: 18,
            child: SizedBox(
              width: 148,
              child: EditorialImagePlaceholder(
                label: 'Vintage drop',
                subtitle: 'Curated photo set',
                badge: 'Hero',
                height: 188,
                borderRadius: 28,
                accentColor: AppColors.accent,
              ),
            ),
          ),
          Positioned(
            left: 18,
            bottom: 18,
            child: Row(
              children: List.generate(
                3,
                (index) => Container(
                  width: index == 0 ? 26 : 6,
                  height: 6,
                  margin: EdgeInsets.only(right: index == 2 ? 0 : 6),
                  decoration: BoxDecoration(
                    color: index == 0 ? AppColors.primary : AppColors.primary.withOpacity(0.24),
                    borderRadius: BorderRadius.circular(999),
                  ),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _CategoryGrid extends StatelessWidget {
  const _CategoryGrid();

  @override
  Widget build(BuildContext context) {
    const categories = <_CategoryItem>[
      _CategoryItem('Tech', Icons.devices_rounded),
      _CategoryItem('Wear', Icons.checkroom_rounded),
      _CategoryItem('Home', Icons.chair_rounded),
      _CategoryItem('Games', Icons.sports_esports_rounded),
      _CategoryItem('Books', Icons.menu_book_rounded),
      _CategoryItem('Luxe', Icons.auto_awesome_rounded),
      _CategoryItem('Photo', Icons.camera_alt_rounded),
      _CategoryItem('Sports', Icons.directions_bike_rounded),
      _CategoryItem('Kids', Icons.toys_rounded),
      _CategoryItem('More', Icons.grid_view_rounded),
    ];

    return LayoutBuilder(
      builder: (context, constraints) {
        final crossAxisCount = constraints.maxWidth > 420 ? 5 : 4;

        return GridView.builder(
          itemCount: categories.length,
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
            crossAxisCount: crossAxisCount,
            mainAxisSpacing: 14,
            crossAxisSpacing: 10,
            childAspectRatio: constraints.maxWidth > 420 ? 0.84 : 0.92,
          ),
          itemBuilder: (context, index) {
            final item = categories[index];
            return Column(
              children: [
                Container(
                  height: 52,
                  decoration: BoxDecoration(
                    color: AppColors.surface,
                    borderRadius: BorderRadius.circular(16),
                  ),
                  child: Center(
                    child: Icon(item.icon, color: AppColors.text, size: 26),
                  ),
                ),
                const SizedBox(height: 8),
                Text(
                  item.label.toUpperCase(),
                  textAlign: TextAlign.center,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: Theme.of(context).textTheme.labelSmall?.copyWith(
                        letterSpacing: 0.8,
                        color: AppColors.text,
                      ),
                ),
              ],
            );
          },
        );
      },
    );
  }
}

class _CategoryItem {
  const _CategoryItem(this.label, this.icon);

  final String label;
  final IconData icon;
}
