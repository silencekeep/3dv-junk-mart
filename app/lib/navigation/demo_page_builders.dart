import 'package:flutter/material.dart';

import '../features/chat/chat_pages.dart';
import '../features/flows/product_flow_pages.dart';
import '../features/profile/profile_settings_page.dart';

typedef DemoPageBuilder = Widget Function(BuildContext context);

Widget buildProductDetailDemoPage(BuildContext context) {
  return ProductDetailPage(
    onOpenOrder: () => Navigator.of(context).push(
      MaterialPageRoute<void>(builder: buildOrderDetailDemoPage),
    ),
    onOpenChat: () => Navigator.of(context).push(
      MaterialPageRoute<void>(builder: buildChatDetailDemoPage),
    ),
    onOpenReview: () => Navigator.of(context).push(
      MaterialPageRoute<void>(builder: buildReviewDemoPage),
    ),
    onOpenSuccess: () => Navigator.of(context).push(
      MaterialPageRoute<void>(builder: buildPaymentSuccessDemoPage),
    ),
  );
}

Widget buildOrderDetailDemoPage(BuildContext context) {
  return const OrderDetailPage();
}

Widget buildChatDetailDemoPage(BuildContext context) {
  return const ChatDetailPage();
}

Widget buildReviewDemoPage(BuildContext context) {
  return const ReviewPage();
}

Widget buildPaymentSuccessDemoPage(BuildContext context) {
  return const PaymentSuccessPage();
}

Widget buildProfileSettingsDemoPage(BuildContext context) {
  return ProfileSettingsPage(
    onSave: () => Navigator.of(context).pop(),
  );
}
