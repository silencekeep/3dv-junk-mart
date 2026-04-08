// ignore_for_file: deprecated_member_use

import 'package:flutter/material.dart';

import '../../theme/app_colors.dart';
import '../../widgets/editorial_widgets.dart';

class MessagesPage extends StatelessWidget {
  const MessagesPage({super.key, required this.onOpenChat});

  final VoidCallback onOpenChat;

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      bottom: false,
      child: Column(
        children: [
          const SizedBox(height: 12),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16),
            child: Row(
              children: [
                const CircleAvatar(
                  radius: 21,
                  backgroundColor: AppColors.surface,
                  child: Icon(Icons.person_rounded, color: AppColors.textMuted),
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
                            'Search conversations...',
                            style: TextStyle(
                              color: AppColors.textMuted,
                              fontSize: 13,
                              fontWeight: FontWeight.w500,
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
                  child: Icon(Icons.notifications_none_rounded, color: AppColors.textMuted),
                ),
              ],
            ),
          ),
          const SizedBox(height: 16),
          Expanded(
            child: ListView(
              padding: const EdgeInsets.fromLTRB(16, 0, 16, 18),
              children: [
                _PreviewCard(onOpenChat: onOpenChat),
                const SizedBox(height: 16),
                EditorialSectionHeader(
                  title: 'Recent threads',
                  actionLabel: 'All',
                ),
                const SizedBox(height: 12),
                _ThreadTile(
                  name: 'Julian Thorne',
                  message: 'Can you ship it today if I buy it now?',
                  time: '2m',
                  highlight: true,
                  onTap: onOpenChat,
                ),
                _ThreadTile(
                  name: 'Sarah L.',
                  message: 'I\'ll take the headphones if they include the case.',
                  time: '14m',
                  onTap: onOpenChat,
                ),
                _ThreadTile(
                  name: 'Marcus J.',
                  message: 'What\'s the lens condition and serial range?',
                  time: '1h',
                  onTap: onOpenChat,
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _PreviewCard extends StatelessWidget {
  const _PreviewCard({required this.onOpenChat});

  final VoidCallback onOpenChat;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: AppColors.primary,
      borderRadius: BorderRadius.circular(28),
      child: InkWell(
        onTap: onOpenChat,
        borderRadius: BorderRadius.circular(28),
        child: Container(
          padding: const EdgeInsets.all(18),
          decoration: BoxDecoration(
            gradient: const LinearGradient(
              colors: [AppColors.primary, Color(0xFF4A493D)],
            ),
            borderRadius: BorderRadius.circular(28),
          ),
          child: Row(
            children: [
              SizedBox(
                width: 58,
                height: 58,
                child: EditorialImagePlaceholder(
                  label: 'Camera bag',
                  subtitle: 'Preview',
                  badge: 'Item',
                  height: 58,
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
                      'Vintage Leather Camera Bag',
                      style: Theme.of(context).textTheme.titleMedium?.copyWith(color: Colors.white),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      'Seller replied 2 minutes ago. Open the thread to continue the purchase.',
                      style: Theme.of(context).textTheme.bodySmall?.copyWith(
                            color: Colors.white70,
                            height: 1.4,
                          ),
                    ),
                    const SizedBox(height: 12),
                    EditorialPill(
                      label: 'Active now',
                      backgroundColor: Colors.white.withOpacity(0.16),
                      foregroundColor: Colors.white,
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 10),
              const Icon(Icons.chevron_right_rounded, color: Colors.white70),
            ],
          ),
        ),
      ),
    );
  }
}

class _ThreadTile extends StatelessWidget {
  const _ThreadTile({
    required this.name,
    required this.message,
    required this.time,
    required this.onTap,
    this.highlight = false,
  });

  final String name;
  final String message;
  final String time;
  final VoidCallback onTap;
  final bool highlight;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Material(
        color: highlight ? AppColors.surface : AppColors.surfaceSoft,
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
                    color: highlight ? AppColors.accent : AppColors.surfaceRaised,
                    shape: BoxShape.circle,
                  ),
                  child: const Icon(Icons.person_rounded, color: AppColors.textMuted),
                ),
                const SizedBox(width: 14),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Expanded(
                            child: Text(name, style: Theme.of(context).textTheme.titleMedium),
                          ),
                          Text(time, style: Theme.of(context).textTheme.labelSmall),
                        ],
                      ),
                      const SizedBox(height: 4),
                      Text(
                        message,
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                        style: Theme.of(context).textTheme.bodySmall?.copyWith(height: 1.35),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class ChatDetailPage extends StatelessWidget {
  const ChatDetailPage({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      body: SafeArea(
        child: Column(
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 12, 16, 12),
              child: Row(
                children: [
                  EditorialRoundIconButton(
                    icon: Icons.arrow_back_rounded,
                    onTap: () => Navigator.pop(context),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text('LuxeCurator', style: Theme.of(context).textTheme.headlineSmall),
                        const SizedBox(height: 2),
                        Row(
                          children: [
                            Container(
                              width: 8,
                              height: 8,
                              decoration: const BoxDecoration(
                                color: AppColors.mint,
                                shape: BoxShape.circle,
                              ),
                            ),
                            const SizedBox(width: 6),
                            Text('Active now', style: Theme.of(context).textTheme.labelSmall),
                          ],
                        ),
                      ],
                    ),
                  ),
                  EditorialRoundIconButton(
                    icon: Icons.more_horiz_rounded,
                    onTap: () {},
                  ),
                ],
              ),
            ),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              child: Container(
                decoration: BoxDecoration(
                  color: AppColors.surface,
                  borderRadius: BorderRadius.circular(20),
                  boxShadow: const [
                    BoxShadow(color: Color(0x10000000), blurRadius: 18, offset: Offset(0, 8)),
                  ],
                ),
                child: Row(
                  children: [
                      SizedBox(
                        width: 84,
                        height: 84,
                        child: EditorialImagePlaceholder(
                          label: 'Camera bag',
                          subtitle: 'Tap to open',
                          badge: 'Preview',
                          height: 84,
                          borderRadius: 20,
                          accentColor: AppColors.surfaceRaised,
                          compact: true,
                        ),
                      ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text('Vintage Leather Camera Bag', style: Theme.of(context).textTheme.titleMedium),
                          const SizedBox(height: 4),
                          Text('\$245', style: Theme.of(context).textTheme.titleLarge?.copyWith(color: AppColors.coral)),
                          const SizedBox(height: 8),
                          Text('Tap to open the product detail screen', style: Theme.of(context).textTheme.bodySmall),
                        ],
                      ),
                    ),
                    const SizedBox(width: 12),
                    const Padding(
                      padding: EdgeInsets.only(right: 12),
                      child: Icon(Icons.arrow_forward_ios_rounded, size: 16, color: AppColors.textMuted),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 12),
            const _NoticeBanner(
              icon: Icons.shield_rounded,
              text: 'Safety Tip: Always trade through the platform to stay protected.',
            ),
            const SizedBox(height: 12),
            Expanded(
              child: ListView(
                padding: const EdgeInsets.fromLTRB(16, 0, 16, 20),
                children: const [
                  _MessageBubble(
                    avatar: 'SC',
                    text: 'Hello! Yes, the camera bag is still available and in excellent condition.',
                    incoming: true,
                  ),
                  SizedBox(height: 12),
                  _MessageBubble(
                    avatar: 'ME',
                    text: 'Great! Can you ship it today if I buy it now?',
                    incoming: false,
                  ),
                  SizedBox(height: 12),
                  _MessageBubble(
                    avatar: 'SC',
                    text: 'Absolutely, I can drop it off at the courier in an hour.',
                    incoming: true,
                  ),
                ],
              ),
            ),
            _ChatDock(onSend: () {}),
          ],
        ),
      ),
    );
  }
}

class _NoticeBanner extends StatelessWidget {
  const _NoticeBanner({required this.icon, required this.text});

  final IconData icon;
  final String text;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
        decoration: BoxDecoration(
          color: AppColors.surface,
          borderRadius: BorderRadius.circular(999),
        ),
        child: Row(
          children: [
            Icon(icon, color: AppColors.mint, size: 18),
            const SizedBox(width: 10),
            Expanded(
              child: Text(text, style: Theme.of(context).textTheme.bodySmall),
            ),
          ],
        ),
      ),
    );
  }
}

class _MessageBubble extends StatelessWidget {
  const _MessageBubble({required this.avatar, required this.text, required this.incoming});

  final String avatar;
  final String text;
  final bool incoming;

  @override
  Widget build(BuildContext context) {
    return Align(
      alignment: incoming ? Alignment.centerLeft : Alignment.centerRight,
      child: Row(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.end,
        children: [
          if (incoming) ...[
            CircleAvatar(
              radius: 16,
              backgroundColor: AppColors.surfaceRaised,
              child: Text(avatar, style: Theme.of(context).textTheme.labelSmall),
            ),
            const SizedBox(width: 8),
          ],
          Container(
            constraints: BoxConstraints(maxWidth: MediaQuery.of(context).size.width * 0.72),
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
            decoration: BoxDecoration(
              color: incoming ? AppColors.surfaceRaised : AppColors.accent,
              borderRadius: BorderRadius.only(
                topLeft: const Radius.circular(20),
                topRight: const Radius.circular(20),
                bottomLeft: Radius.circular(incoming ? 4 : 20),
                bottomRight: Radius.circular(incoming ? 20 : 4),
              ),
            ),
            child: Text(
              text,
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    height: 1.4,
                    color: AppColors.text,
                  ),
            ),
          ),
          if (!incoming) ...[
            const SizedBox(width: 8),
            CircleAvatar(
              radius: 16,
              backgroundColor: AppColors.accent,
              child: Text(
                avatar,
                style: Theme.of(context).textTheme.labelSmall?.copyWith(
                      color: AppColors.primary,
                    ),
              ),
            ),
          ],
        ],
      ),
    );
  }
}

class _ChatDock extends StatelessWidget {
  const _ChatDock({required this.onSend});

  final VoidCallback onSend;

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      top: false,
      child: Padding(
        padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
        child: Container(
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            color: Colors.white.withOpacity(0.92),
            borderRadius: BorderRadius.circular(28),
            boxShadow: const [
              BoxShadow(color: Color(0x10000000), blurRadius: 18, offset: Offset(0, 6)),
            ],
          ),
          child: Row(
            children: [
              const Icon(Icons.add_circle_outline_rounded, color: AppColors.textMuted),
              const SizedBox(width: 8),
              Expanded(
                child: TextField(
                  decoration: const InputDecoration(
                    hintText: 'Type your message...',
                    fillColor: AppColors.surfaceSoft,
                    filled: true,
                  ),
                ),
              ),
              const SizedBox(width: 8),
              IconButton(
                onPressed: onSend,
                icon: const Icon(Icons.send_rounded, color: AppColors.primary),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
