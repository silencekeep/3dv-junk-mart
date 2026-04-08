// ignore_for_file: deprecated_member_use

import 'package:flutter/material.dart';

import '../chat/chat_pages.dart';
import '../home/home_page.dart';
import '../profile/profile_page.dart';
import '../search/search_page.dart';
import '../sell/sell_page.dart';
import '../../navigation/demo_page_builders.dart';
import '../../theme/app_colors.dart';

class AppShell extends StatefulWidget {
  const AppShell({super.key, required this.onSignOut});

  final VoidCallback onSignOut;

  @override
  State<AppShell> createState() => _AppShellState();
}

class _AppShellState extends State<AppShell> {
  int _selectedIndex = 0;

  void _selectTab(int index) {
    setState(() {
      _selectedIndex = index;
    });
  }

  void _openPage(DemoPageBuilder pageBuilder) {
    Navigator.of(context).push(
      MaterialPageRoute<void>(builder: pageBuilder),
    );
  }

  @override
  Widget build(BuildContext context) {
    final pages = <Widget>[
      HomePage(
        onGoSearch: () => _selectTab(1),
        onOpenDetail: () => _openPage(buildProductDetailDemoPage),
        onOpenOrder: () => _openPage(buildOrderDetailDemoPage),
        onOpenChat: () => _openPage(buildChatDetailDemoPage),
        onOpenReview: () => _openPage(buildReviewDemoPage),
        onOpenSuccess: () => _openPage(buildPaymentSuccessDemoPage),
      ),
      SearchPage(
        onGoHome: () => _selectTab(0),
        onOpenDetail: () => _openPage(buildProductDetailDemoPage),
      ),
      SellPage(
        onGoHome: () => _selectTab(0),
        onOpenSuccess: () => _openPage(buildPaymentSuccessDemoPage),
        onOpenReview: () => _openPage(buildReviewDemoPage),
      ),
      MessagesPage(
        onOpenChat: () => _openPage(buildChatDetailDemoPage),
      ),
      ProfilePage(
        onOpenOrder: () => _openPage(buildOrderDetailDemoPage),
        onOpenReview: () => _openPage(buildReviewDemoPage),
        onOpenSuccess: () => _openPage(buildPaymentSuccessDemoPage),
        onOpenSettings: () => _openPage(buildProfileSettingsDemoPage),
        onSignOut: widget.onSignOut,
      ),
    ];

    return Scaffold(
      body: IndexedStack(
        index: _selectedIndex,
        children: pages,
      ),
      bottomNavigationBar: SafeArea(
        top: false,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(12, 0, 12, 12),
          child: Container(
            height: 82,
            decoration: BoxDecoration(
              color: Colors.white.withOpacity(0.88),
              borderRadius: BorderRadius.circular(30),
              border: Border.all(color: Colors.white.withOpacity(0.72)),
              boxShadow: const [
                BoxShadow(
                  color: Color(0x14000000),
                  blurRadius: 28,
                  offset: Offset(0, -2),
                ),
              ],
            ),
            child: Row(
              children: [
                Expanded(
                  child: _NavItem(
                    label: 'Home',
                    icon: Icons.home_rounded,
                    selected: _selectedIndex == 0,
                    onTap: () => _selectTab(0),
                  ),
                ),
                Expanded(
                  child: _NavItem(
                    label: 'Search',
                    icon: Icons.manage_search_rounded,
                    selected: _selectedIndex == 1,
                    onTap: () => _selectTab(1),
                  ),
                ),
                Expanded(
                  child: Transform.translate(
                    offset: const Offset(0, -14),
                    child: GestureDetector(
                      onTap: () => _selectTab(2),
                      child: Column(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          Container(
                            width: 56,
                            height: 56,
                            decoration: BoxDecoration(
                              color: AppColors.accent,
                              shape: BoxShape.circle,
                              boxShadow: const [
                                BoxShadow(
                                  color: Color(0x33FFD83D),
                                  blurRadius: 22,
                                  offset: Offset(0, 8),
                                ),
                              ],
                            ),
                            child: const Icon(Icons.add_rounded, color: AppColors.primary, size: 30),
                          ),
                          const SizedBox(height: 4),
                          Text(
                            'Post',
                            style: Theme.of(context).textTheme.labelSmall?.copyWith(
                                  color: AppColors.text,
                                  fontWeight: FontWeight.w800,
                                ),
                          ),
                        ],
                      ),
                    ),
                  ),
                ),
                Expanded(
                  child: _NavItem(
                    label: 'Chat',
                    icon: Icons.chat_bubble_rounded,
                    selected: _selectedIndex == 3,
                    onTap: () => _selectTab(3),
                  ),
                ),
                Expanded(
                  child: _NavItem(
                    label: 'Profile',
                    icon: Icons.person_rounded,
                    selected: _selectedIndex == 4,
                    onTap: () => _selectTab(4),
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

class _NavItem extends StatelessWidget {
  const _NavItem({
    required this.label,
    required this.icon,
    required this.selected,
    required this.onTap,
  });

  final String label;
  final IconData icon;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final foreground = selected ? AppColors.text : AppColors.textMuted;
    return InkResponse(
      onTap: onTap,
      radius: 44,
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(icon, color: foreground, size: selected ? 28 : 24),
          const SizedBox(height: 4),
          Text(
            label,
            style: Theme.of(context).textTheme.labelSmall?.copyWith(
                  color: foreground,
                  fontWeight: selected ? FontWeight.w800 : FontWeight.w600,
                ),
          ),
        ],
      ),
    );
  }
}
