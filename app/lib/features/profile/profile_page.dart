// ignore_for_file: deprecated_member_use

import 'package:flutter/material.dart';

import '../../theme/app_colors.dart';
import '../../widgets/editorial_widgets.dart';

class ProfilePage extends StatelessWidget {
  const ProfilePage({
    super.key,
    required this.onOpenOrder,
    required this.onOpenReview,
    required this.onOpenSuccess,
    required this.onOpenSettings,
    required this.onSignOut,
  });

  final VoidCallback onOpenOrder;
  final VoidCallback onOpenReview;
  final VoidCallback onOpenSuccess;
  final VoidCallback onOpenSettings;
  final VoidCallback onSignOut;

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      bottom: false,
      child: ListView(
        key: const PageStorageKey<String>('profile-list'),
        padding: const EdgeInsets.fromLTRB(16, 16, 16, 128),
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              EditorialRoundIconButton(
                icon: Icons.settings_rounded,
                onTap: onOpenSettings,
              ),
              Text('Profile', style: Theme.of(context).textTheme.titleLarge),
              EditorialRoundIconButton(
                icon: Icons.qr_code_scanner_rounded,
                onTap: () {},
              ),
            ],
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
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                SizedBox(
                  width: 100,
                  height: 100,
                  child: EditorialImagePlaceholder(
                    label: 'Julian Thorne',
                    subtitle: 'Collector profile',
                    badge: 'My page',
                    height: 100,
                    borderRadius: 28,
                    accentColor: AppColors.accent,
                  ),
                ),
                const SizedBox(width: 14),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('Julian Thorne', style: Theme.of(context).textTheme.headlineSmall),
                      const SizedBox(height: 6),
                      Text(
                        'Collector, seller, and weekend curator',
                        style: Theme.of(context).textTheme.bodySmall,
                      ),
                      const SizedBox(height: 10),
                      EditorialPill(
                        label: 'Sesame credit: excellent',
                        backgroundColor: const Color(0xFFE0F7F7),
                        foregroundColor: AppColors.mint,
                      ),
                      const SizedBox(height: 12),
                      Wrap(
                        spacing: 20,
                        runSpacing: 12,
                        children: const [
                          _ProfileMetric(value: '128', label: 'Following'),
                          _ProfileMetric(value: '2.4k', label: 'Followers'),
                          _ProfileMetric(value: '98%', label: 'Positive'),
                        ],
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 14),
          _StatsPanel(
            metrics: const [
              _MetricItem(label: 'I\'ve posted', value: '12', icon: Icons.edit_rounded),
              _MetricItem(label: 'I\'ve sold', value: '8', icon: Icons.sell_rounded),
              _MetricItem(label: 'I\'ve bought', value: '15', icon: Icons.shopping_bag_rounded),
              _MetricItem(label: 'I\'ve liked', value: '24', icon: Icons.favorite_rounded),
            ],
          ),
          const SizedBox(height: 16),
          EditorialSectionHeader(
            title: 'My listings',
            actionLabel: 'Live 4',
            onActionTap: () {},
          ),
          const SizedBox(height: 12),
          SizedBox(
            height: 262,
            child: ListView.separated(
              scrollDirection: Axis.horizontal,
              itemCount: 3,
              separatorBuilder: (context, index) => const SizedBox(width: 12),
              itemBuilder: (context, index) {
                final listings = <_ListingItem>[
                  const _ListingItem(
                    title: 'Vintage Leather Camera Bag',
                    price: '¥245',
                    status: 'Live now',
                    accentColor: AppColors.accent,
                  ),
                  const _ListingItem(
                    title: 'Studio Headphones Mk. II',
                    price: '¥340',
                    status: 'In review',
                    accentColor: AppColors.surfaceRaised,
                  ),
                  const _ListingItem(
                    title: 'Classic Red Runners',
                    price: '¥95',
                    status: 'Draft saved',
                    accentColor: AppColors.mint,
                  ),
                ];

                final listing = listings[index];
                return SizedBox(
                  width: 220,
                  child: _ListingCard(item: listing),
                );
              },
            ),
          ),
          const SizedBox(height: 16),
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: AppColors.accent,
              borderRadius: BorderRadius.circular(24),
              boxShadow: const [
                BoxShadow(color: Color(0x18FFD83D), blurRadius: 18, offset: Offset(0, 8)),
              ],
            ),
            child: Row(
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('VIP membership', style: Theme.of(context).textTheme.titleLarge?.copyWith(color: AppColors.primary)),
                      const SizedBox(height: 6),
                      Text(
                        'Unlock exclusive seller benefits',
                        style: Theme.of(context).textTheme.bodySmall?.copyWith(color: AppColors.primary.withOpacity(0.82)),
                      ),
                      const SizedBox(height: 12),
                      TextButton(
                        onPressed: onOpenSuccess,
                        child: const Text('Upgrade now'),
                      ),
                    ],
                  ),
                ),
                const SizedBox(width: 12),
                SizedBox(
                  width: 86,
                  height: 86,
                  child: EditorialImagePlaceholder(
                    label: 'VIP',
                    subtitle: 'Benefits',
                    badge: 'Club',
                    height: 86,
                    borderRadius: 22,
                    accentColor: Colors.white.withOpacity(0.34),
                    compact: true,
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 16),
          EditorialSectionHeader(
            title: 'My services',
            actionLabel: 'Tools',
            onActionTap: () {},
          ),
          const SizedBox(height: 12),
          _ServicesPanel(
            tiles: const [
              _ServiceTile(icon: Icons.waves_rounded, label: 'Fish pond'),
              _ServiceTile(icon: Icons.autorenew_rounded, label: 'Old for new'),
              _ServiceTile(icon: Icons.admin_panel_settings_rounded, label: 'Safety center'),
              _ServiceTile(icon: Icons.support_agent_rounded, label: 'Support'),
              _ServiceTile(icon: Icons.rate_review_rounded, label: 'My reviews'),
              _ServiceTile(icon: Icons.group_add_rounded, label: 'Invite friends'),
              _ServiceTile(icon: Icons.local_activity_rounded, label: 'Vouchers'),
              _ServiceTile(icon: Icons.location_on_rounded, label: 'Address'),
            ],
          ),
          const SizedBox(height: 16),
          EditorialActionCard(
            title: 'Profile settings',
            subtitle: 'Avatar, nickname, age, and location',
            icon: Icons.person_outline_rounded,
            onTap: onOpenSettings,
          ),
          EditorialActionCard(
            title: 'Order timeline',
            subtitle: 'Review logistics and payment breakdown',
            icon: Icons.local_shipping_rounded,
            onTap: onOpenOrder,
          ),
          EditorialActionCard(
            title: 'Leave a review',
            subtitle: 'Open the post-review flow',
            icon: Icons.rate_review_rounded,
            onTap: onOpenReview,
          ),
          EditorialActionCard(
            title: 'Success flow',
            subtitle: 'Preview wallet confirmation and recommendations',
            icon: Icons.verified_rounded,
            onTap: onOpenSuccess,
          ),
          EditorialActionCard(
            title: 'Sign out',
            subtitle: 'Return to the authentication screen',
            icon: Icons.logout_rounded,
            onTap: onSignOut,
          ),
        ],
      ),
    );
  }
}

class _ProfileMetric extends StatelessWidget {
  const _ProfileMetric({required this.value, required this.label});

  final String value;
  final String label;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(value, style: Theme.of(context).textTheme.titleMedium),
        Text(label, style: Theme.of(context).textTheme.bodySmall),
      ],
    );
  }
}

class _StatsPanel extends StatelessWidget {
  const _StatsPanel({required this.metrics});

  final List<_MetricItem> metrics;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final crossAxisCount = constraints.maxWidth > 420 ? 4 : 2;

        return Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: AppColors.surface,
            borderRadius: BorderRadius.circular(24),
            boxShadow: const [
              BoxShadow(color: Color(0x10000000), blurRadius: 24, offset: Offset(0, 10)),
            ],
          ),
          child: GridView.count(
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            crossAxisCount: crossAxisCount,
            crossAxisSpacing: 12,
            mainAxisSpacing: 12,
            childAspectRatio: 0.92,
            children: metrics
                .map(
                  (metric) => Column(
                    children: [
                      Container(
                        width: 52,
                        height: 52,
                        decoration: BoxDecoration(
                          color: AppColors.surfaceSoft,
                          shape: BoxShape.circle,
                        ),
                        child: Icon(metric.icon, color: AppColors.textMuted),
                      ),
                      const SizedBox(height: 8),
                      Text(metric.label, textAlign: TextAlign.center, style: Theme.of(context).textTheme.labelSmall),
                      const SizedBox(height: 4),
                      Text(metric.value, style: Theme.of(context).textTheme.titleSmall),
                    ],
                  ),
                )
                .toList(growable: false),
          ),
        );
      },
    );
  }
}

class _MetricItem {
  const _MetricItem({required this.label, required this.value, required this.icon});

  final String label;
  final String value;
  final IconData icon;
}

class _ListingItem {
  const _ListingItem({required this.title, required this.price, required this.status, required this.accentColor});

  final String title;
  final String price;
  final String status;
  final Color accentColor;
}

class _ListingCard extends StatelessWidget {
  const _ListingCard({required this.item});

  final _ListingItem item;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(24),
        boxShadow: const [
          BoxShadow(color: Color(0x10000000), blurRadius: 22, offset: Offset(0, 10)),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Expanded(
            child: EditorialImagePlaceholder(
              label: 'Photo preview',
              subtitle: item.status,
              badge: item.status,
              accentColor: item.accentColor,
              borderRadius: 22,
            ),
          ),
          const SizedBox(height: 12),
          Text(
            item.title,
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
            style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                  fontWeight: FontWeight.w700,
                  height: 1.3,
                ),
          ),
          const SizedBox(height: 8),
          Row(
            children: [
              Text(item.price, style: Theme.of(context).textTheme.titleLarge?.copyWith(color: AppColors.coral)),
              const Spacer(),
              Text(item.status, style: Theme.of(context).textTheme.labelSmall),
            ],
          ),
        ],
      ),
    );
  }
}

class _ServicesPanel extends StatelessWidget {
  const _ServicesPanel({required this.tiles});

  final List<_ServiceTile> tiles;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final crossAxisCount = constraints.maxWidth > 420 ? 4 : 3;

        return Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: AppColors.surface,
            borderRadius: BorderRadius.circular(24),
            boxShadow: const [
              BoxShadow(color: Color(0x10000000), blurRadius: 24, offset: Offset(0, 10)),
            ],
          ),
          child: GridView.count(
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            crossAxisCount: crossAxisCount,
            mainAxisSpacing: 16,
            crossAxisSpacing: 10,
            childAspectRatio: 0.92,
            children: tiles,
          ),
        );
      },
    );
  }
}

class _ServiceTile extends StatelessWidget {
  const _ServiceTile({required this.icon, required this.label});

  final IconData icon;
  final String label;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Container(
          width: 46,
          height: 46,
          decoration: BoxDecoration(
            color: AppColors.surfaceSoft,
            borderRadius: BorderRadius.circular(16),
          ),
          child: Icon(icon, color: AppColors.primary),
        ),
        const SizedBox(height: 8),
        Text(label, textAlign: TextAlign.center, style: Theme.of(context).textTheme.bodySmall),
      ],
    );
  }
}
