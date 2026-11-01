import 'package:flutter/material.dart';

/// Shared Material roles for discovery, evidence and account surfaces.
ThemeData signSightTheme(Brightness brightness) {
  final dark = brightness == Brightness.dark;
  final scheme =
      ColorScheme.fromSeed(
        seedColor: const Color(0xff245c48),
        brightness: brightness,
      ).copyWith(
        primary: dark ? const Color(0xffa5d3b9) : const Color(0xff245c48),
        onPrimary: dark ? const Color(0xff083826) : Colors.white,
        primaryContainer: dark
            ? const Color(0xff244f3d)
            : const Color(0xffdceadf),
        onPrimaryContainer: dark
            ? const Color(0xffdceadf)
            : const Color(0xff153d2b),
        surface: dark ? const Color(0xff121813) : const Color(0xfff5f6f1),
        surfaceContainerLow: dark
            ? const Color(0xff1a211b)
            : const Color(0xffeef1e9),
        surfaceContainer: dark
            ? const Color(0xff202820)
            : const Color(0xffe9ede4),
        surfaceContainerHigh: dark
            ? const Color(0xff2a322b)
            : const Color(0xffe2e8dc),
        onSurface: dark ? const Color(0xffe3e9df) : const Color(0xff25342b),
        onSurfaceVariant: dark
            ? const Color(0xffbdc9bd)
            : const Color(0xff536157),
        outlineVariant: dark
            ? const Color(0xff414d43)
            : const Color(0xffd4ddd1),
      );
  final base = ThemeData(useMaterial3: true, colorScheme: scheme);
  final text = base.textTheme.copyWith(
    headlineSmall: base.textTheme.headlineSmall?.copyWith(
      fontWeight: FontWeight.w700,
    ),
    titleLarge: base.textTheme.titleLarge?.copyWith(
      fontWeight: FontWeight.w700,
    ),
    titleMedium: base.textTheme.titleMedium?.copyWith(
      fontWeight: FontWeight.w600,
    ),
    bodyMedium: base.textTheme.bodyMedium?.copyWith(height: 1.5),
    bodySmall: base.textTheme.bodySmall?.copyWith(height: 1.4),
  );
  const shape = RoundedRectangleBorder(
    borderRadius: BorderRadius.all(Radius.circular(14)),
  );
  return base.copyWith(
    scaffoldBackgroundColor: scheme.surface,
    textTheme: text,
    appBarTheme: AppBarTheme(
      backgroundColor: scheme.surface,
      foregroundColor: scheme.onSurface,
      surfaceTintColor: Colors.transparent,
      scrolledUnderElevation: 0,
      centerTitle: false,
      titleSpacing: 20,
      titleTextStyle: text.titleLarge?.copyWith(color: scheme.onSurface),
    ),
    navigationBarTheme: NavigationBarThemeData(
      backgroundColor: scheme.surface,
      surfaceTintColor: Colors.transparent,
      indicatorColor: scheme.primaryContainer,
      height: 80,
      labelTextStyle: WidgetStateProperty.resolveWith(
        (states) => text.labelMedium?.copyWith(
          color: states.contains(WidgetState.selected)
              ? scheme.primary
              : scheme.onSurfaceVariant,
          fontWeight: states.contains(WidgetState.selected)
              ? FontWeight.w700
              : FontWeight.w500,
        ),
      ),
    ),
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        minimumSize: const Size(48, 52),
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 14),
        shape: shape,
      ),
    ),
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(
        minimumSize: const Size(48, 52),
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 14),
        shape: shape,
        side: BorderSide(color: scheme.outlineVariant),
      ),
    ),
    textButtonTheme: TextButtonThemeData(
      style: TextButton.styleFrom(
        minimumSize: const Size(48, 48),
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      ),
    ),
    iconButtonTheme: IconButtonThemeData(
      style: IconButton.styleFrom(minimumSize: const Size(48, 48)),
    ),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: scheme.surfaceContainerLow,
      contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 16),
      border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(12),
        borderSide: BorderSide(color: scheme.outlineVariant),
      ),
    ),
    chipTheme: base.chipTheme.copyWith(
      side: BorderSide(color: scheme.outlineVariant),
      selectedColor: scheme.primaryContainer,
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 8),
    ),
    dividerTheme: DividerThemeData(
      color: scheme.outlineVariant,
      space: 32,
      thickness: 1,
    ),
    bottomSheetTheme: BottomSheetThemeData(
      backgroundColor: scheme.surface,
      surfaceTintColor: Colors.transparent,
      showDragHandle: true,
    ),
    listTileTheme: ListTileThemeData(
      iconColor: scheme.onSurfaceVariant,
      contentPadding: const EdgeInsets.symmetric(horizontal: 20, vertical: 8),
    ),
  );
}
