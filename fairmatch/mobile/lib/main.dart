import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'app.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  // Errors are shown to the user with an explicit retry action instead of silent auto-retries.
  runApp(ProviderScope(retry: (_, _) => null, child: const FairMatchApp()));
}
