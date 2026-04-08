// ignore_for_file: deprecated_member_use

import 'package:flutter/material.dart';

import 'app_colors.dart';

ThemeData buildAppTheme() {
  final base = ThemeData.light();
  final colorScheme = ColorScheme.fromSeed(
    seedColor: AppColors.accent,
    brightness: Brightness.light,
  ).copyWith(
    primary: AppColors.primary,
    onPrimary: Colors.white,
    secondary: AppColors.accentDeep,
    onSecondary: Colors.white,
    tertiary: AppColors.mint,
    onTertiary: Colors.white,
    error: AppColors.coral,
    onError: Colors.white,
    surface: AppColors.surface,
    onSurface: AppColors.text,
    onSurfaceVariant: AppColors.textMuted,
    outline: AppColors.border,
    outlineVariant: AppColors.surfaceRaised,
    inverseSurface: AppColors.primary,
    onInverseSurface: AppColors.surface,
    inversePrimary: AppColors.accent,
    surfaceTint: AppColors.accent,
  );

  final textTheme = base.textTheme.copyWith(
    displayLarge: base.textTheme.displayLarge?.copyWith(
      fontFamily: 'Georgia',
      fontSize: 56,
      fontWeight: FontWeight.w700,
      height: 0.95,
      letterSpacing: -1.8,
      color: AppColors.text,
    ),
    displayMedium: base.textTheme.displayMedium?.copyWith(
      fontFamily: 'Georgia',
      fontSize: 44,
      fontWeight: FontWeight.w700,
      height: 1,
      letterSpacing: -1.5,
      color: AppColors.text,
    ),
    displaySmall: base.textTheme.displaySmall?.copyWith(
      fontFamily: 'Georgia',
      fontSize: 34,
      fontWeight: FontWeight.w700,
      height: 1,
      letterSpacing: -1.1,
      color: AppColors.text,
    ),
    headlineLarge: base.textTheme.headlineLarge?.copyWith(
      fontFamily: 'Georgia',
      fontSize: 30,
      fontWeight: FontWeight.w700,
      letterSpacing: -0.8,
      color: AppColors.text,
    ),
    headlineMedium: base.textTheme.headlineMedium?.copyWith(
      fontFamily: 'Georgia',
      fontSize: 24,
      fontWeight: FontWeight.w700,
      letterSpacing: -0.5,
      color: AppColors.text,
    ),
    headlineSmall: base.textTheme.headlineSmall?.copyWith(
      fontFamily: 'Georgia',
      fontSize: 20,
      fontWeight: FontWeight.w700,
      letterSpacing: -0.2,
      color: AppColors.text,
    ),
    titleLarge: base.textTheme.titleLarge?.copyWith(
      fontFamily: 'Georgia',
      fontSize: 18,
      fontWeight: FontWeight.w700,
      letterSpacing: -0.1,
      color: AppColors.text,
    ),
    titleMedium: base.textTheme.titleMedium?.copyWith(
      fontFamily: 'Georgia',
      fontSize: 16,
      fontWeight: FontWeight.w700,
      letterSpacing: 0,
      color: AppColors.text,
    ),
    titleSmall: base.textTheme.titleSmall?.copyWith(
      fontFamily: 'Georgia',
      fontSize: 14,
      fontWeight: FontWeight.w700,
      color: AppColors.text,
    ),
    bodyLarge: base.textTheme.bodyLarge?.copyWith(
      fontSize: 16,
      height: 1.45,
      color: AppColors.text,
    ),
    bodyMedium: base.textTheme.bodyMedium?.copyWith(
      fontSize: 14,
      height: 1.45,
      color: AppColors.text,
    ),
    bodySmall: base.textTheme.bodySmall?.copyWith(
      fontSize: 12,
      height: 1.35,
      color: AppColors.textMuted,
    ),
    labelLarge: base.textTheme.labelLarge?.copyWith(
      fontSize: 13,
      fontWeight: FontWeight.w700,
      letterSpacing: 0.6,
      color: AppColors.text,
    ),
    labelMedium: base.textTheme.labelMedium?.copyWith(
      fontSize: 11,
      fontWeight: FontWeight.w700,
      letterSpacing: 0.8,
      color: AppColors.textMuted,
    ),
    labelSmall: base.textTheme.labelSmall?.copyWith(
      fontSize: 10,
      fontWeight: FontWeight.w700,
      letterSpacing: 0.9,
      color: AppColors.textMuted,
    ),
  );

  return ThemeData(
    useMaterial3: true,
    brightness: Brightness.light,
    colorScheme: colorScheme,
    fontFamily: 'Georgia',
    scaffoldBackgroundColor: AppColors.background,
    textTheme: textTheme,
    appBarTheme: const AppBarTheme(
      backgroundColor: Colors.transparent,
      surfaceTintColor: Colors.transparent,
      elevation: 0,
      scrolledUnderElevation: 0,
      centerTitle: false,
    ),
    cardTheme: CardThemeData(
      color: AppColors.surface,
      elevation: 0,
      margin: EdgeInsets.zero,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(24),
      ),
    ),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: AppColors.surface,
      hintStyle: textTheme.bodyMedium?.copyWith(color: AppColors.textMuted.withOpacity(0.55)),
      contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(22),
        borderSide: BorderSide.none,
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(22),
        borderSide: BorderSide.none,
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(22),
        borderSide: const BorderSide(color: AppColors.accentDeep, width: 1.4),
      ),
    ),
    elevatedButtonTheme: ElevatedButtonThemeData(
      style: ElevatedButton.styleFrom(
        backgroundColor: AppColors.primary,
        foregroundColor: Colors.white,
        elevation: 0,
        minimumSize: const Size.fromHeight(54),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(18)),
        textStyle: textTheme.labelLarge?.copyWith(
          color: Colors.white,
          fontWeight: FontWeight.w800,
        ),
      ),
    ),
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        backgroundColor: AppColors.accent,
        foregroundColor: AppColors.primary,
        elevation: 0,
        minimumSize: const Size.fromHeight(54),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(18)),
        textStyle: textTheme.labelLarge?.copyWith(
          color: AppColors.primary,
          fontWeight: FontWeight.w800,
        ),
      ),
    ),
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(
        foregroundColor: AppColors.text,
        side: const BorderSide(color: AppColors.border),
        minimumSize: const Size.fromHeight(54),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(18)),
        textStyle: textTheme.labelLarge?.copyWith(
          color: AppColors.text,
          fontWeight: FontWeight.w700,
        ),
      ),
    ),
    textButtonTheme: TextButtonThemeData(
      style: TextButton.styleFrom(
        foregroundColor: AppColors.text,
        textStyle: textTheme.labelLarge?.copyWith(
          color: AppColors.text,
          fontWeight: FontWeight.w700,
        ),
      ),
    ),
    chipTheme: ChipThemeData(
      backgroundColor: AppColors.surfaceSoft,
      selectedColor: AppColors.accent,
      disabledColor: AppColors.surfaceRaised,
      labelStyle: textTheme.labelMedium,
      side: BorderSide.none,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(999)),
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
    ),
    dividerTheme: const DividerThemeData(
      color: AppColors.surfaceRaised,
      thickness: 1,
      space: 1,
    ),
  );
}
