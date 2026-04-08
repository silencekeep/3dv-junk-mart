// ignore_for_file: deprecated_member_use

import 'package:flutter/material.dart';

import '../../theme/app_colors.dart';
import '../../widgets/editorial_widgets.dart';

class ProductDetailPage extends StatelessWidget {
  const ProductDetailPage({
    super.key,
    required this.onOpenOrder,
    required this.onOpenChat,
    required this.onOpenReview,
    required this.onOpenSuccess,
  });

  final VoidCallback onOpenOrder;
  final VoidCallback onOpenChat;
  final VoidCallback onOpenReview;
  final VoidCallback onOpenSuccess;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 128),
          children: [
            EditorialScreenHeader(
              title: 'Product detail',
              onBack: () => Navigator.pop(context),
              trailing: EditorialRoundIconButton(
                icon: Icons.share_rounded,
                onTap: () {},
              ),
            ),
            const SizedBox(height: 16),
            _HeroPanel(
              title: 'Vintage Leather Camera Bag',
              subtitle: 'Backpack-friendly size, limited release, excellent condition.',
            ),
            const SizedBox(height: 16),
            _PricePanel(
              currentPrice: '\$245',
              oldPrice: '\$320',
              discountLabel: '70% off',
              title: 'Vintage Leather Artisan Camera Bag - 1980s Limited Edition',
            ),
            const SizedBox(height: 16),
            _SellerPanel(onOpenChat: onOpenChat),
            const SizedBox(height: 16),
            _SpecGrid(
              items: const [
                _SpecItem(label: 'Brand', value: 'Leica'),
                _SpecItem(label: 'Condition', value: '95% new'),
                _SpecItem(label: 'Location', value: 'Manhattan, NY'),
                _SpecItem(label: 'Shipping', value: 'Free priority'),
              ],
            ),
            const SizedBox(height: 16),
            const _BodyCard(
              title: 'Description',
              children: [
                Text(
                  'Meticulously cared for Leica M6 Classic. This is the version with the .72x viewfinder. Body is in exceptional condition with only minor bright marks on the baseplate. The vulcanite is original and perfectly intact.',
                ),
                SizedBox(height: 12),
                Text(
                  'Included is the legendary Summicron 35mm f/2 lens. Optics are clean, free of fungus or haze. Aperture blades are snappy and dry.',
                ),
                SizedBox(height: 12),
                Text(
                  'Reason for selling: moving to a medium format system for gallery work. Open to serious inquiries only.',
                ),
              ],
            ),
            const SizedBox(height: 16),
            _InquiryCard(
              onOpenReview: onOpenReview,
            ),
            const SizedBox(height: 16),
            _ActionRow(
              children: [
                _ActionButton(
                  label: 'Chat',
                  icon: Icons.chat_bubble_rounded,
                  onPressed: onOpenChat,
                ),
                _ActionButton(
                  label: 'Want',
                  icon: Icons.favorite_rounded,
                  onPressed: onOpenReview,
                ),
                _ActionButton(
                  label: 'Buy now',
                  icon: Icons.shopping_bag_rounded,
                  filled: true,
                  onPressed: onOpenOrder,
                ),
              ],
            ),
            const SizedBox(height: 12),
            TextButton(
              onPressed: onOpenSuccess,
              child: const Text('Preview success flow'),
            ),
          ],
        ),
      ),
    );
  }
}

class OrderDetailPage extends StatelessWidget {
  const OrderDetailPage({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 128),
          children: [
            EditorialScreenHeader(
              title: 'Order details',
              onBack: () => Navigator.pop(context),
              trailing: EditorialRoundIconButton(
                icon: Icons.more_horiz_rounded,
                onTap: () {},
              ),
            ),
            const SizedBox(height: 16),
            Container(
              padding: const EdgeInsets.all(18),
              decoration: BoxDecoration(
                color: AppColors.accent.withOpacity(0.18),
                borderRadius: BorderRadius.circular(26),
              ),
              child: Row(
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text('Status', style: Theme.of(context).textTheme.labelSmall?.copyWith(color: AppColors.primary)),
                        const SizedBox(height: 4),
                        Text('Seller shipped', style: Theme.of(context).textTheme.headlineSmall),
                        const SizedBox(height: 6),
                        Text('Expected delivery in 2-3 business days', style: Theme.of(context).textTheme.bodySmall),
                      ],
                    ),
                  ),
                  Container(
                    width: 72,
                    height: 72,
                    decoration: const BoxDecoration(
                      color: AppColors.accent,
                      shape: BoxShape.circle,
                    ),
                    child: const Icon(Icons.local_shipping_rounded, color: AppColors.primary, size: 34),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 16),
            _BodyCard(
              title: 'Shipping address',
              children: const [
                _InfoLine(label: 'Alex Rivera', value: '+1 (555) 012-3456'),
                SizedBox(height: 8),
                Text('1282 Editorial Lane, Apt 4B\nNew York, NY 10001, United States'),
                SizedBox(height: 14),
                _LogisticsUpdate(),
              ],
            ),
            const SizedBox(height: 16),
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: AppColors.surface,
                borderRadius: BorderRadius.circular(24),
                boxShadow: const [
                  BoxShadow(color: Color(0x10000000), blurRadius: 24, offset: Offset(0, 10)),
                ],
              ),
              child: Row(
                children: [
                  SizedBox(
                    width: 88,
                    height: 88,
                    child: EditorialImagePlaceholder(
                      label: 'Item preview',
                      subtitle: 'Sold out soon',
                      badge: 'Listing',
                      height: 88,
                      borderRadius: 18,
                      accentColor: AppColors.surfaceRaised,
                      compact: true,
                    ),
                  ),
                  const SizedBox(width: 14),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        EditorialPill(
                          label: 'Like new',
                          backgroundColor: const Color(0x1A1F7A68),
                          foregroundColor: AppColors.mint,
                        ),
                        const SizedBox(height: 8),
                        Text(
                          'Vintage Leather Artisan Camera Bag - 1980s Limited Edition',
                          style: Theme.of(context).textTheme.titleMedium,
                        ),
                        const SizedBox(height: 8),
                        Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            Text('245.00 credits', style: Theme.of(context).textTheme.headlineSmall?.copyWith(color: AppColors.text)),
                            Text('Qty: 1', style: Theme.of(context).textTheme.bodySmall),
                          ],
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 16),
            const _BodyCard(
              title: 'Order information',
              children: [
                _InfoLine(label: 'Order ID', value: 'TXN-8829-0012', copyIcon: true),
                SizedBox(height: 12),
                _InfoLine(label: 'Transaction time', value: 'Oct 22, 2023 11:32:09'),
                SizedBox(height: 12),
                _InfoLine(label: 'Payment method', value: 'Editorial wallet (credit)', valueIcon: Icons.account_balance_wallet_rounded),
              ],
            ),
            const SizedBox(height: 16),
            const _BodyCard(
              title: 'Price breakdown',
              children: [
                _InfoLine(label: 'Item price', value: '245.00'),
                SizedBox(height: 8),
                _InfoLine(label: 'Shipping fee', value: '12.00'),
                SizedBox(height: 8),
                _InfoLine(label: 'Editorial discount', value: '-5.00', valueColor: AppColors.mint),
                SizedBox(height: 14),
                Divider(color: AppColors.surfaceRaised),
                SizedBox(height: 10),
                _InfoLine(label: 'Total paid', value: '252.00', valueIcon: Icons.account_balance_wallet_rounded, emphasize: true),
              ],
            ),
          ],
        ),
      ),
      bottomNavigationBar: SafeArea(
        top: false,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
          child: Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: Colors.white.withOpacity(0.92),
              borderRadius: BorderRadius.circular(28),
              boxShadow: const [
                BoxShadow(color: Color(0x10000000), blurRadius: 24, offset: Offset(0, -2)),
              ],
            ),
            child: Row(
              children: [
                Expanded(child: OutlinedButton(onPressed: () {}, child: const Text('Contact seller'))),
                const SizedBox(width: 10),
                Expanded(child: OutlinedButton(onPressed: () {}, child: const Text('View logistics'))),
                const SizedBox(width: 10),
                Expanded(child: FilledButton(onPressed: () {}, child: const Text('Confirm receipt'))),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class ReviewPage extends StatefulWidget {
  const ReviewPage({super.key});

  @override
  State<ReviewPage> createState() => _ReviewPageState();
}

class _ReviewPageState extends State<ReviewPage> {
  int _rating = 5;
  bool _anonymous = false;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 128),
          children: [
            EditorialScreenHeader(
              title: 'Post review',
              onBack: () => Navigator.pop(context),
              trailing: EditorialRoundIconButton(
                icon: Icons.more_horiz_rounded,
                onTap: () {},
              ),
            ),
            const SizedBox(height: 16),
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: AppColors.surface,
                borderRadius: BorderRadius.circular(24),
                boxShadow: const [
                  BoxShadow(color: Color(0x10000000), blurRadius: 24, offset: Offset(0, 10)),
                ],
              ),
              child: Row(
                children: [
                  SizedBox(
                    width: 72,
                    height: 72,
                    child: EditorialImagePlaceholder(
                      label: 'Order item',
                      subtitle: 'Preview',
                      badge: 'Photo',
                      height: 72,
                      borderRadius: 18,
                      accentColor: AppColors.surfaceRaised,
                      compact: true,
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text('Vintage 1990s Camel Leather Carryall', style: Theme.of(context).textTheme.titleMedium),
                        const SizedBox(height: 6),
                        Text('Ordered Oct 12, 2023', style: Theme.of(context).textTheme.bodySmall),
                      ],
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 16),
            _BodyCard(
              title: 'Your rating',
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: List.generate(5, (index) {
                    final selected = index < _rating;
                    return GestureDetector(
                      onTap: () {
                        setState(() {
                          _rating = index + 1;
                        });
                      },
                      child: Icon(
                        selected ? Icons.star_rounded : Icons.star_outline_rounded,
                        color: selected ? AppColors.accentDeep : AppColors.textMuted.withOpacity(0.35),
                        size: 36,
                      ),
                    );
                  }),
                ),
                const SizedBox(height: 12),
                Text('Tap a star to set the rating.', style: Theme.of(context).textTheme.bodySmall),
              ],
            ),
            const SizedBox(height: 16),
            _BodyCard(
              title: 'Review tags',
              children: [
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: [
                    _ReviewTag(label: 'Great quality', selected: true, onTap: () {}),
                    _ReviewTag(label: 'Careful packaging', onTap: () {}),
                    _ReviewTag(label: 'Fast delivery', onTap: () {}),
                    _ReviewTag(label: 'Friendly seller', onTap: () {}),
                  ],
                ),
              ],
            ),
            const SizedBox(height: 16),
            const _PhotoRow(),
            const SizedBox(height: 16),
            _BodyCard(
              title: 'Review text',
              children: [
                TextField(
                  maxLines: 6,
                  decoration: InputDecoration(
                    hintText: 'Share your experience with the seller and item quality...',
                    filled: false,
                    fillColor: Colors.transparent,
                    contentPadding: EdgeInsets.zero,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 16),
            _BodyCard(
              title: 'Privacy',
              children: [
                SwitchListTile.adaptive(
                  contentPadding: EdgeInsets.zero,
                  value: _anonymous,
                  onChanged: (value) {
                    setState(() {
                      _anonymous = value;
                    });
                  },
                  title: const Text('Post anonymously'),
                  subtitle: Text(
                    'Your profile will still record the review privately.',
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 16),
            FilledButton(
              onPressed: () {},
              child: const Text('Submit review'),
            ),
          ],
        ),
      ),
    );
  }
}

class PaymentSuccessPage extends StatelessWidget {
  const PaymentSuccessPage({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 128),
          children: [
            EditorialScreenHeader(
              title: 'Order complete',
              onBack: () => Navigator.pop(context),
              trailing: EditorialRoundIconButton(
                icon: Icons.receipt_long_rounded,
                onTap: () {},
              ),
            ),
            const SizedBox(height: 16),
            Container(
              padding: const EdgeInsets.all(22),
              decoration: BoxDecoration(
                color: AppColors.accent,
                borderRadius: BorderRadius.circular(32),
                boxShadow: const [
                  BoxShadow(color: Color(0x24FFD83D), blurRadius: 28, offset: Offset(0, 14)),
                ],
              ),
              child: Column(
                children: [
                  Container(
                    width: 88,
                    height: 88,
                    decoration: const BoxDecoration(
                      color: Colors.white,
                      shape: BoxShape.circle,
                    ),
                    child: const Icon(Icons.check_rounded, color: AppColors.primary, size: 50),
                  ),
                  const SizedBox(height: 18),
                  Text('Payment successful', style: Theme.of(context).textTheme.headlineMedium?.copyWith(color: AppColors.primary)),
                  const SizedBox(height: 8),
                  Text('Your order has been created and the seller has been notified.', textAlign: TextAlign.center, style: Theme.of(context).textTheme.bodyMedium?.copyWith(color: AppColors.primary.withOpacity(0.84))),
                  const SizedBox(height: 16),
                  EditorialPill(
                    label: 'Order #TXN-8829-0012',
                    backgroundColor: Colors.white.withOpacity(0.42),
                    foregroundColor: AppColors.primary,
                  ),
                ],
              ),
            ),
            const SizedBox(height: 16),
            _BodyCard(
              title: 'Receipt summary',
              children: const [
                _InfoLine(label: 'Paid by', value: 'Editorial Wallet'),
                SizedBox(height: 10),
                _InfoLine(label: 'Amount', value: '¥252.00', valueIcon: Icons.account_balance_wallet_rounded, emphasize: true),
                SizedBox(height: 10),
                _InfoLine(label: 'Estimated delivery', value: '2-3 business days'),
              ],
            ),
            const SizedBox(height: 16),
            _BodyCard(
              title: 'Next steps',
              children: const [
                _NextStep(label: 'Track shipping updates in the order detail page.'),
                SizedBox(height: 10),
                _NextStep(label: 'Stay in touch with the seller through chat.'),
                SizedBox(height: 10),
                _NextStep(label: 'Leave a review after the item arrives.'),
              ],
            ),
            const SizedBox(height: 16),
            const _RecommendationGrid(),
          ],
        ),
      ),
      bottomNavigationBar: SafeArea(
        top: false,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
          child: Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: Colors.white.withOpacity(0.92),
              borderRadius: BorderRadius.circular(28),
              boxShadow: const [
                BoxShadow(color: Color(0x10000000), blurRadius: 24, offset: Offset(0, -2)),
              ],
            ),
            child: LayoutBuilder(
              builder: (context, constraints) {
                final isCompact = constraints.maxWidth < 420;

                if (!isCompact) {
                  return Row(
                    children: [
                      Expanded(child: OutlinedButton(onPressed: () {}, child: const Text('Contact seller'))),
                      const SizedBox(width: 10),
                      Expanded(child: OutlinedButton(onPressed: () {}, child: const Text('View logistics'))),
                      const SizedBox(width: 10),
                      Expanded(child: FilledButton(onPressed: () {}, child: const Text('Confirm receipt'))),
                    ],
                  );
                }

                return Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Row(
                      children: [
                        Expanded(child: OutlinedButton(onPressed: () {}, child: const Text('Contact seller'))),
                        const SizedBox(width: 10),
                        Expanded(child: OutlinedButton(onPressed: () {}, child: const Text('View logistics'))),
                      ],
                    ),
                    const SizedBox(height: 10),
                    SizedBox(
                      width: double.infinity,
                      child: FilledButton(onPressed: () {}, child: const Text('Confirm receipt')),
                    ),
                  ],
                );
              },
            ),
          ),
        ),
      ),
    );
  }
}

class _HeroPanel extends StatelessWidget {
  const _HeroPanel({required this.title, required this.subtitle});

  final String title;
  final String subtitle;

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 344,
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          colors: [Color(0xFFF6EFC2), Color(0xFFD6CF9C), Color(0xFFF0E7C8)],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(32),
        boxShadow: const [
          BoxShadow(color: Color(0x18000000), blurRadius: 28, offset: Offset(0, 14)),
        ],
      ),
      child: Stack(
        children: [
          Positioned(
            left: 18,
            top: 72,
            right: 132,
            child: Text(
              title,
              maxLines: 3,
              overflow: TextOverflow.ellipsis,
              style: Theme.of(context).textTheme.displaySmall?.copyWith(
                    color: AppColors.primary,
                    height: 0.94,
                  ),
            ),
          ),
          Positioned(
            left: 18,
            top: 188,
            right: 132,
            child: Text(
              subtitle,
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    color: AppColors.primary.withOpacity(0.8),
                    height: 1.45,
                  ),
            ),
          ),
          Positioned(
            right: -36,
            bottom: -24,
            child: Container(
              width: 188,
              height: 188,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: Colors.white.withOpacity(0.24),
              ),
            ),
          ),
          Positioned(
            right: 18,
            top: 18,
            child: EditorialPill(
              label: 'Limited drop',
              backgroundColor: Colors.white.withOpacity(0.5),
              foregroundColor: AppColors.primary,
            ),
          ),
          Positioned(
            right: 18,
            top: 58,
            bottom: 18,
            child: SizedBox(
              width: 164,
              child: EditorialImagePlaceholder(
                label: 'Gallery preview',
                subtitle: 'Open photos',
                badge: 'Hero',
                height: 228,
                borderRadius: 28,
                accentColor: AppColors.accent,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _PricePanel extends StatelessWidget {
  const _PricePanel({
    required this.currentPrice,
    required this.oldPrice,
    required this.discountLabel,
    required this.title,
  });

  final String currentPrice;
  final String oldPrice;
  final String discountLabel;
  final String title;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(24),
        boxShadow: const [
          BoxShadow(color: Color(0x10000000), blurRadius: 24, offset: Offset(0, 10)),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Text(currentPrice, style: Theme.of(context).textTheme.displaySmall?.copyWith(color: AppColors.coral)),
              const SizedBox(width: 12),
              Text(
                oldPrice,
                style: Theme.of(context).textTheme.titleMedium?.copyWith(
                      color: AppColors.textMuted,
                      decoration: TextDecoration.lineThrough,
                    ),
              ),
              const Spacer(),
              EditorialPill(
                label: discountLabel,
                filled: true,
              ),
            ],
          ),
          const SizedBox(height: 10),
          Text(title, style: Theme.of(context).textTheme.titleMedium),
        ],
      ),
    );
  }
}

class _SellerPanel extends StatelessWidget {
  const _SellerPanel({required this.onOpenChat});

  final VoidCallback onOpenChat;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.surfaceSoft,
        borderRadius: BorderRadius.circular(24),
      ),
      child: Row(
        children: [
          Container(
            width: 68,
            height: 68,
            decoration: BoxDecoration(
              color: AppColors.surfaceRaised,
              borderRadius: BorderRadius.circular(22),
            ),
            child: const Icon(Icons.person_rounded, color: AppColors.textMuted, size: 32),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Text('Julian Thorne', style: Theme.of(context).textTheme.titleMedium),
                    const SizedBox(width: 8),
                    EditorialPill(
                      label: 'Trusted',
                      backgroundColor: const Color(0xFFE0F7F7),
                      foregroundColor: AppColors.mint,
                    ),
                  ],
                ),
                const SizedBox(height: 6),
                Row(
                  children: [
                    const Icon(Icons.credit_score_rounded, size: 16, color: AppColors.textMuted),
                    const SizedBox(width: 4),
                    Text('Sesame 780', style: Theme.of(context).textTheme.bodySmall),
                    const SizedBox(width: 10),
                    Container(width: 4, height: 4, decoration: const BoxDecoration(color: AppColors.border, shape: BoxShape.circle)),
                    const SizedBox(width: 10),
                    Text('Active 2m ago', style: Theme.of(context).textTheme.bodySmall?.copyWith(color: AppColors.mint)),
                  ],
                ),
              ],
            ),
          ),
          const SizedBox(width: 10),
          TextButton(onPressed: onOpenChat, child: const Text('Follow')),
        ],
      ),
    );
  }
}

class _SpecGrid extends StatelessWidget {
  const _SpecGrid({required this.items});

  final List<_SpecItem> items;

  @override
  Widget build(BuildContext context) {
    return GridView.count(
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      crossAxisCount: 2,
      mainAxisSpacing: 12,
      crossAxisSpacing: 12,
      childAspectRatio: 2.1,
      children: items
          .map(
            (item) => Container(
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(
                color: AppColors.surface,
                borderRadius: BorderRadius.circular(20),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Text(item.label.toUpperCase(), style: Theme.of(context).textTheme.labelSmall?.copyWith(color: AppColors.textMuted)),
                  const SizedBox(height: 6),
                  Text(item.value, style: Theme.of(context).textTheme.titleMedium),
                ],
              ),
            ),
          )
          .toList(growable: false),
    );
  }
}

class _SpecItem {
  const _SpecItem({required this.label, required this.value});

  final String label;
  final String value;
}

class _BodyCard extends StatelessWidget {
  const _BodyCard({required this.title, required this.children});

  final String title;
  final List<Widget> children;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(24),
        boxShadow: const [
          BoxShadow(color: Color(0x10000000), blurRadius: 24, offset: Offset(0, 10)),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title, style: Theme.of(context).textTheme.headlineSmall),
          const SizedBox(height: 12),
          ...children,
        ],
      ),
    );
  }
}

class _InquiryCard extends StatelessWidget {
  const _InquiryCard({required this.onOpenReview});

  final VoidCallback onOpenReview;

  @override
  Widget build(BuildContext context) {
    return _BodyCard(
      title: 'Inquiries (12)',
      children: [
        Container(
          padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(
            color: AppColors.surfaceSoft,
            borderRadius: BorderRadius.circular(20),
          ),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              CircleAvatar(
                radius: 16,
                backgroundColor: AppColors.surfaceRaised,
                child: Text('M', style: Theme.of(context).textTheme.labelSmall),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Text('Marcus L.', style: Theme.of(context).textTheme.labelLarge),
                        const Spacer(),
                        Text('2h ago', style: Theme.of(context).textTheme.labelSmall),
                      ],
                    ),
                    const SizedBox(height: 6),
                    Text('Has the light meter been recently calibrated? Is the battery door corroded?', style: Theme.of(context).textTheme.bodySmall?.copyWith(height: 1.4)),
                  ],
                ),
              ),
            ],
          ),
        ),
        const SizedBox(height: 10),
        Padding(
          padding: const EdgeInsets.only(left: 32),
          child: Container(
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(
              color: AppColors.surface,
              borderRadius: BorderRadius.circular(18),
              border: Border.all(color: AppColors.surfaceRaised),
            ),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 3),
                  decoration: BoxDecoration(
                    color: AppColors.accent,
                    borderRadius: BorderRadius.circular(6),
                  ),
                  child: Text('SELLER', style: Theme.of(context).textTheme.labelSmall?.copyWith(fontWeight: FontWeight.w800)),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: Text('Light meter is perfect, recently checked against a Sekonic. No corrosion at all, very clean.', style: Theme.of(context).textTheme.bodySmall?.copyWith(height: 1.4)),
                ),
              ],
            ),
          ),
        ),
        const SizedBox(height: 10),
        TextButton(onPressed: onOpenReview, child: const Text('Preview review flow')),
      ],
    );
  }
}

class _ActionRow extends StatelessWidget {
  const _ActionRow({required this.children});

  final List<Widget> children;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: List<Widget>.generate(
        children.length,
        (index) => Expanded(
          child: Padding(
            padding: EdgeInsets.only(right: index == children.length - 1 ? 0 : 10),
            child: children[index],
          ),
        ),
      ),
    );
  }
}

class _ActionButton extends StatelessWidget {
  const _ActionButton({
    required this.label,
    required this.icon,
    required this.onPressed,
    this.filled = false,
  });

  final String label;
  final IconData icon;
  final VoidCallback onPressed;
  final bool filled;

  @override
  Widget build(BuildContext context) {
    return FilledButton.tonal(
      style: FilledButton.styleFrom(
        backgroundColor: filled ? AppColors.accent : AppColors.surfaceSoft,
        foregroundColor: AppColors.text,
        minimumSize: const Size.fromHeight(54),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(18)),
      ),
      onPressed: onPressed,
      child: Row(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(icon, size: 18),
          const SizedBox(width: 8),
          Text(label),
        ],
      ),
    );
  }
}

class _InfoLine extends StatelessWidget {
  const _InfoLine({
    required this.label,
    required this.value,
    this.valueIcon,
    this.copyIcon = false,
    this.emphasize = false,
    this.valueColor,
  });

  final String label;
  final String value;
  final IconData? valueIcon;
  final bool copyIcon;
  final bool emphasize;
  final Color? valueColor;

  @override
  Widget build(BuildContext context) {
    final valueStyle = emphasize
        ? Theme.of(context).textTheme.headlineSmall?.copyWith(color: valueColor ?? AppColors.text)
        : Theme.of(context).textTheme.bodyMedium?.copyWith(
              color: valueColor ?? AppColors.text,
              fontWeight: FontWeight.w600,
            );
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Text(label, style: Theme.of(context).textTheme.bodySmall),
        const SizedBox(width: 12),
        Flexible(
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              if (valueIcon != null) ...[
                Icon(valueIcon, size: emphasize ? 22 : 18, color: valueColor ?? AppColors.primary),
                const SizedBox(width: 6),
              ],
              Flexible(
                child: Text(
                  value,
                  textAlign: TextAlign.end,
                  style: valueStyle,
                ),
              ),
              if (copyIcon) ...[
                const SizedBox(width: 6),
                const Icon(Icons.content_copy_rounded, size: 16, color: AppColors.textMuted),
              ],
            ],
          ),
        ),
      ],
    );
  }
}

class _LogisticsUpdate extends StatelessWidget {
  const _LogisticsUpdate();

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(20),
      ),
      child: Row(
        children: [
          Container(
            width: 44,
            height: 44,
            decoration: const BoxDecoration(color: AppColors.mint, shape: BoxShape.circle),
            child: const Icon(Icons.inventory_2_rounded, color: Colors.white, size: 20),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Text('Logistics update', style: Theme.of(context).textTheme.titleSmall),
                    const Spacer(),
                    EditorialPill(
                      label: 'Transit',
                      backgroundColor: const Color(0x1A1F7A68),
                      foregroundColor: AppColors.mint,
                    ),
                  ],
                ),
                const SizedBox(height: 6),
                Text('Arrived at regional distribution center', style: Theme.of(context).textTheme.bodySmall),
                const SizedBox(height: 2),
                Text('Oct 24, 2023 · 02:45 PM', style: Theme.of(context).textTheme.labelSmall),
              ],
            ),
          ),
          const Icon(Icons.chevron_right_rounded, color: AppColors.textMuted),
        ],
      ),
    );
  }
}

class _PhotoRow extends StatelessWidget {
  const _PhotoRow();

  @override
  Widget build(BuildContext context) {
    return _BodyCard(
      title: 'Add photos',
      children: [
        GridView.count(
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          crossAxisCount: 3,
          mainAxisSpacing: 10,
          crossAxisSpacing: 10,
          childAspectRatio: 0.9,
          children: const [
            EditorialImagePlaceholder(
              label: 'Main shot',
              subtitle: 'Front view',
              badge: 'Main',
              accentColor: AppColors.accent,
              borderRadius: 18,
            ),
            EditorialImagePlaceholder(
              label: 'Gallery set',
              subtitle: 'Detail shots',
              badge: 'More',
              accentColor: AppColors.surfaceRaised,
              borderRadius: 18,
            ),
            EditorialImagePlaceholder(
              label: 'Video cover',
              subtitle: '30 sec clip',
              badge: 'Clip',
              accentColor: AppColors.surfaceSoft,
              borderRadius: 18,
            ),
          ],
        ),
      ],
    );
  }
}

class _ReviewTag extends StatelessWidget {
  const _ReviewTag({required this.label, required this.onTap, this.selected = false});

  final String label;
  final VoidCallback onTap;
  final bool selected;

  @override
  Widget build(BuildContext context) {
    return ChoiceChip(
      label: Text(label),
      selected: selected,
      onSelected: (_) => onTap(),
      labelStyle: Theme.of(context).textTheme.labelMedium?.copyWith(
            color: selected ? AppColors.primary : AppColors.textMuted,
          ),
    );
  }
}

class _NextStep extends StatelessWidget {
  const _NextStep({required this.label});

  final String label;

  @override
  Widget build(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Container(
          width: 22,
          height: 22,
          decoration: const BoxDecoration(
            color: AppColors.accent,
            shape: BoxShape.circle,
          ),
          child: const Icon(Icons.check_rounded, size: 14, color: AppColors.primary),
        ),
        const SizedBox(width: 10),
        Expanded(
          child: Text(label, style: Theme.of(context).textTheme.bodyMedium),
        ),
      ],
    );
  }
}

class _RecommendationGrid extends StatelessWidget {
  const _RecommendationGrid();

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        EditorialSectionHeader(
          title: 'Recommended for you',
          actionLabel: 'More',
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
                    title: 'Another vintage camera accessory',
                    price: '\$80',
                    location: 'Osaka',
                    icon: Icons.photo_camera_rounded,
                    tag: 'New',
                    accentColor: AppColors.surfaceSoft,
                    onTap: () {},
                  ),
                ),
                SizedBox(
                  width: cardWidth,
                  child: EditorialProductCard(
                    title: 'Classic leather shoulder strap',
                    price: '\$28',
                    location: 'Berlin',
                    icon: Icons.shopping_bag_rounded,
                    tag: 'Popular',
                    accentColor: AppColors.surfaceRaised,
                    tall: true,
                    onTap: () {},
                  ),
                ),
              ],
            );
          },
        ),
      ],
    );
  }
}
