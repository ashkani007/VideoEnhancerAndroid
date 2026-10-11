import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';
import 'package:uuid/uuid.dart';

import '../../core/theme.dart';
import '../../data/models.dart';
import '../../data/repository.dart';
import '../../state/providers.dart';
import '../../widgets/common.dart';
import '../discover/profile_detail_screen.dart';
import '../profile/safety_sheet.dart';

class ChatScreen extends ConsumerStatefulWidget {
  const ChatScreen({super.key, required this.matchId, this.match});
  final String matchId;
  final MatchItem? match;

  @override
  ConsumerState<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends ConsumerState<ChatScreen> {
  final _input = TextEditingController();
  final _scroll = ScrollController();
  final List<ChatMessage> _messages = [];
  StreamSubscription<RealtimeEvent>? _sub;
  Timer? _typingTimer;
  DateTime _lastTypingSent = DateTime(2000);
  bool _loading = true, _loadingOlder = false, _hasMore = true, _theyTyping = false;
  Object? _error;
  MatchItem? _match;

  FairMatchRepository get _repo => ref.read(repoProvider);

  @override
  void initState() {
    super.initState();
    _match = widget.match;
    _sub = _repo.events.listen(_onEvent);
    _scroll.addListener(() {
      if (_scroll.position.pixels >= _scroll.position.maxScrollExtent - 200) _loadOlder();
    });
    _load();
  }

  @override
  void dispose() {
    _sub?.cancel();
    _typingTimer?.cancel();
    _input.dispose();
    _scroll.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    try {
      _match ??= (await _repo.matches()).where((m) => m.matchId == widget.matchId).firstOrNull;
      final msgs = await _repo.messages(widget.matchId);
      setState(() {
        _messages
          ..clear()
          ..addAll(msgs);
        _loading = false;
        _error = null;
        _hasMore = msgs.length >= 30;
      });
      _markRead();
    } catch (e) {
      setState(() {
        _loading = false;
        _error = e;
      });
    }
  }

  /// Offline recovery: fetch anything newer than the last message we have.
  Future<void> _catchUp() async {
    final last = _messages.where((m) => m.id > 0).lastOrNull;
    if (last == null) return _load();
    try {
      final newer = await _repo.messages(widget.matchId, afterId: last.id);
      setState(() => _merge(newer));
      _markRead();
    } catch (_) {}
  }

  Future<void> _loadOlder() async {
    if (_loadingOlder || !_hasMore || _messages.isEmpty) return;
    _loadingOlder = true;
    try {
      final first = _messages.where((m) => m.id > 0).firstOrNull;
      if (first == null) return;
      final older = await _repo.messages(widget.matchId, beforeId: first.id);
      setState(() {
        _messages.insertAll(0, older);
        _hasMore = older.length >= 30;
      });
    } catch (_) {
    } finally {
      _loadingOlder = false;
    }
  }

  void _merge(List<ChatMessage> incoming) {
    for (final m in incoming) {
      final i = _messages.indexWhere((x) => x.id == m.id || (x.clientMessageId == m.clientMessageId && x.senderId == m.senderId));
      if (i >= 0) {
        _messages[i] = m;
      } else {
        _messages.add(m);
      }
    }
    _messages.sort((a, b) => (a.id < 0 ? 1 << 40 : a.id).compareTo(b.id < 0 ? 1 << 40 : b.id));
  }

  void _onEvent(RealtimeEvent e) {
    if (!mounted) return;
    switch (e) {
      case MessageEvent(:final message) when message.matchId == widget.matchId:
        setState(() {
          _theyTyping = false;
          _merge([message]);
        });
        _markRead();
      case TypingEvent(:final matchId) when matchId == widget.matchId:
        setState(() => _theyTyping = true);
        _typingTimer?.cancel();
        _typingTimer = Timer(const Duration(seconds: 4), () => mounted ? setState(() => _theyTyping = false) : null);
      case ReadEvent(:final matchId, :final upToId) when matchId == widget.matchId:
        setState(() {
          for (var i = 0; i < _messages.length; i++) {
            final m = _messages[i];
            if (m.id > 0 && m.id <= upToId && m.status != DeliveryStatus.received) _messages[i] = m.copyWith(status: DeliveryStatus.read);
          }
        });
      case MatchClosedEvent(:final matchId) when matchId == widget.matchId:
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('This conversation has ended.')));
        context.pop();
      default:
        break;
    }
  }

  void _markRead() {
    final lastIncoming = _messages.where((m) => m.status == DeliveryStatus.received && m.id > 0).lastOrNull;
    if (lastIncoming != null) {
      _repo.markRead(widget.matchId, lastIncoming.id).catchError((_) {});
      ref.invalidate(matchesProvider);
    }
  }

  Future<void> _send([String? text, ChatMessage? retry]) async {
    final body = (text ?? _input.text).trim();
    if (body.isEmpty) return;
    final local = retry?.copyWith(status: DeliveryStatus.sending) ??
        ChatMessage(
          id: -DateTime.now().microsecondsSinceEpoch,
          matchId: widget.matchId,
          senderId: 'me',
          clientMessageId: const Uuid().v4(),
          body: body,
          createdAt: DateTime.now(),
          status: DeliveryStatus.sending,
        );
    setState(() {
      if (retry == null) {
        _messages.add(local);
        _input.clear();
      } else {
        _messages[_messages.indexWhere((m) => m.clientMessageId == retry.clientMessageId)] = local;
      }
    });
    try {
      final saved = await _repo.sendMessage(widget.matchId, body, local.clientMessageId);
      setState(() {
        _messages.removeWhere((m) => m.clientMessageId == local.clientMessageId && m.id < 0);
        _merge([saved]);
      });
      ref.invalidate(matchesProvider);
    } on ApiException catch (e) {
      setState(() {
        final i = _messages.indexWhere((m) => m.clientMessageId == local.clientMessageId);
        if (i >= 0) _messages[i] = local.copyWith(status: DeliveryStatus.failed);
      });
      if (!e.isOffline && mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.message)));
    }
  }

  void _onChanged(String _) {
    final now = DateTime.now();
    if (now.difference(_lastTypingSent) > const Duration(seconds: 3)) {
      _lastTypingSent = now;
      _repo.sendTyping(widget.matchId);
    }
    setState(() {});
  }

  Future<void> _assist() async {
    final me = await ref.read(meProvider.future);
    if (!mounted) return;
    if (!me.entitlements.aiAssistant) {
      context.push('/subscription');
      return;
    }
    final draft = _input.text.trim();
    if (draft.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Write a draft first — AI will suggest kinder, clearer versions.')));
      return;
    }
    final picked = await showModalBottomSheet<String>(context: context, builder: (_) => _RephraseSheet(draft: draft));
    if (picked != null) {
      _input.text = picked;
      setState(() {});
    }
  }

  @override
  Widget build(BuildContext context) {
    final fm = context.fm;
    final p = _match?.profile;
    final reversed = _messages.reversed.toList();
    return Scaffold(
      appBar: AppBar(
        titleSpacing: 0,
        title: p == null
            ? const Text('Chat')
            : InkWell(
                onTap: () => context.push('/view', extra: ProfileDetailArgs(cards: [p])),
                child: Row(children: [
                  SizedBox(width: 38, height: 38, child: ClipOval(child: Portrait(name: p.firstName, url: p.photos.firstOrNull, borderRadius: 0))),
                  const SizedBox(width: 10),
                  Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Row(children: [
                      Text(p.firstName, style: context.text.titleMedium),
                      if (p.verified) const Padding(padding: EdgeInsets.only(left: 4), child: VerifiedBadge(size: 15)),
                    ]),
                    Text(_theyTyping ? 'typing…' : (p.isDemo ? 'Fictional demo profile' : 'Matched'),
                        style: context.text.bodySmall?.copyWith(color: _theyTyping ? fm.accent : fm.textMuted)),
                  ]),
                ]),
              ),
        actions: [
          if (p != null)
            IconButton(
              tooltip: 'Safety options',
              icon: const Icon(Icons.shield_outlined),
              onPressed: () async {
                final done = await showSafetySheet(context, userId: p.id, name: p.firstName, matchId: widget.matchId);
                if (done == true && context.mounted) context.pop();
              },
            ),
        ],
      ),
      body: Column(children: [
        Expanded(
          child: _loading
              ? const Center(child: CircularProgressIndicator())
              : _error != null
                  ? MessageState.error(_error!, onRetry: () {
                      setState(() => _loading = true);
                      _load();
                    })
                  : RefreshIndicator(
                      onRefresh: _catchUp,
                      child: _messages.isEmpty
                          ? ListView(children: [_EmptyChat(profile: p, onPick: (s) => setState(() => _input.text = s))])
                          : ListView.builder(
                              controller: _scroll,
                              reverse: true,
                              padding: const EdgeInsets.fromLTRB(FmSpace.md, FmSpace.md, FmSpace.md, FmSpace.md),
                              itemCount: reversed.length + (_theyTyping ? 1 : 0),
                              itemBuilder: (_, i) {
                                if (_theyTyping && i == 0) return const _TypingBubble();
                                final m = reversed[i - (_theyTyping ? 1 : 0)];
                                return _Bubble(message: m, onRetry: m.status == DeliveryStatus.failed ? () => _send(m.body, m) : null);
                              },
                            ),
                    ),
        ),
        SafeArea(
          top: false,
          child: Padding(
            padding: const EdgeInsets.fromLTRB(FmSpace.sm, FmSpace.xs, FmSpace.sm, FmSpace.sm),
            child: Row(crossAxisAlignment: CrossAxisAlignment.end, children: [
              IconButton(tooltip: 'AI writing help', onPressed: _assist, icon: Icon(Icons.auto_awesome, color: fm.accent)),
              Expanded(
                child: TextField(
                  controller: _input,
                  minLines: 1,
                  maxLines: 5,
                  maxLength: 2000,
                  buildCounter: (_, {required currentLength, required isFocused, maxLength}) => null,
                  textCapitalization: TextCapitalization.sentences,
                  onChanged: _onChanged,
                  decoration: InputDecoration(
                    hintText: 'Write something thoughtful…',
                    border: OutlineInputBorder(borderRadius: BorderRadius.circular(FmRadius.xl), borderSide: BorderSide.none),
                    enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(FmRadius.xl), borderSide: BorderSide(color: fm.stroke)),
                    focusedBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(FmRadius.xl), borderSide: BorderSide(color: fm.accent)),
                  ),
                ),
              ),
              const SizedBox(width: 6),
              AnimatedScale(
                scale: _input.text.trim().isEmpty ? 0.85 : 1,
                duration: FmMotion.of(context, FmMotion.fast),
                child: IconButton.filled(
                  tooltip: 'Send',
                  onPressed: _input.text.trim().isEmpty ? null : () => _send(),
                  style: IconButton.styleFrom(backgroundColor: fm.accent, minimumSize: const Size(48, 48)),
                  icon: const Icon(Icons.arrow_upward_rounded, color: Colors.white),
                ),
              ),
            ]),
          ),
        ),
      ]),
    );
  }
}

class _Bubble extends StatelessWidget {
  const _Bubble({required this.message, this.onRetry});
  final ChatMessage message;
  final VoidCallback? onRetry;

  @override
  Widget build(BuildContext context) {
    final fm = context.fm;
    final mine = message.status != DeliveryStatus.received;
    final statusIcon = switch (message.status) {
      DeliveryStatus.sending => Icons.schedule_rounded,
      DeliveryStatus.sent => Icons.check_rounded,
      DeliveryStatus.delivered => Icons.done_all_rounded,
      DeliveryStatus.read => Icons.done_all_rounded,
      DeliveryStatus.failed => Icons.error_outline_rounded,
      DeliveryStatus.received => null,
    };
    final statusLabel = switch (message.status) {
      DeliveryStatus.sending => 'Sending',
      DeliveryStatus.sent => 'Sent',
      DeliveryStatus.delivered => 'Delivered',
      DeliveryStatus.read => 'Read',
      DeliveryStatus.failed => 'Not sent. Tap to retry',
      DeliveryStatus.received => '',
    };
    return Align(
      alignment: mine ? Alignment.centerRight : Alignment.centerLeft,
      child: GestureDetector(
        onTap: onRetry,
        child: Semantics(
          label: '${mine ? 'You' : 'Them'}: ${message.body}. $statusLabel',
          child: Container(
            constraints: BoxConstraints(maxWidth: MediaQuery.sizeOf(context).width * 0.76),
            margin: const EdgeInsets.only(bottom: 6),
            padding: const EdgeInsets.fromLTRB(14, 10, 14, 8),
            decoration: BoxDecoration(
              gradient: mine ? fm.brandGradient : null,
              color: mine ? null : fm.surfaceHigh,
              borderRadius: BorderRadius.only(
                topLeft: const Radius.circular(FmRadius.md),
                topRight: const Radius.circular(FmRadius.md),
                bottomLeft: Radius.circular(mine ? FmRadius.md : 4),
                bottomRight: Radius.circular(mine ? 4 : FmRadius.md),
              ),
            ),
            child: Column(crossAxisAlignment: CrossAxisAlignment.end, mainAxisSize: MainAxisSize.min, children: [
              Text(message.body, style: context.text.bodyLarge?.copyWith(color: mine ? Colors.white : fm.text)),
              const SizedBox(height: 3),
              Row(mainAxisSize: MainAxisSize.min, children: [
                Text(DateFormat.Hm().format(message.createdAt),
                    style: TextStyle(fontSize: 10.5, color: mine ? Colors.white70 : fm.textMuted)),
                if (statusIcon != null) ...[
                  const SizedBox(width: 4),
                  Icon(statusIcon, size: 14,
                      color: message.status == DeliveryStatus.read
                          ? const Color(0xFF7DD3FC)
                          : message.status == DeliveryStatus.failed
                              ? Colors.amberAccent
                              : Colors.white70),
                ],
              ]),
            ]),
          ),
        ),
      ),
    );
  }
}

class _TypingBubble extends StatefulWidget {
  const _TypingBubble();
  @override
  State<_TypingBubble> createState() => _TypingBubbleState();
}

class _TypingBubbleState extends State<_TypingBubble> with SingleTickerProviderStateMixin {
  late final AnimationController _c = AnimationController(vsync: this, duration: const Duration(milliseconds: 1100))..repeat();

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final fm = context.fm;
    return Align(
      alignment: Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.only(bottom: 6),
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
        decoration: BoxDecoration(color: fm.surfaceHigh, borderRadius: BorderRadius.circular(FmRadius.md)),
        child: AnimatedBuilder(
          animation: _c,
          builder: (_, _) => Row(mainAxisSize: MainAxisSize.min, children: [
            for (var i = 0; i < 3; i++)
              Container(
                margin: const EdgeInsets.symmetric(horizontal: 2),
                width: 7,
                height: 7,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: fm.textMuted.withValues(alpha: 0.35 + 0.65 * (((_c.value * 3 - i) % 3) < 1 ? 1 : 0)),
                ),
              ),
          ]),
        ),
      ),
    );
  }
}

class _EmptyChat extends StatelessWidget {
  const _EmptyChat({required this.profile, required this.onPick});
  final ProfileCard? profile;
  final ValueChanged<String> onPick;

  @override
  Widget build(BuildContext context) {
    final fm = context.fm;
    final p = profile;
    final starters = [
      if (p != null && p.interests.isNotEmpty) 'You mentioned ${p.interests.first} — how did you get into it?',
      if (p != null && p.prompts.isNotEmpty) 'Your answer to “${p.prompts.first.question}” made me smile. Tell me more?',
      'What does a really good weekend look like for you?',
    ];
    return Padding(
      padding: const EdgeInsets.all(FmSpace.lg),
      child: Column(children: [
        const SizedBox(height: FmSpace.xl),
        if (p != null) SizedBox(width: 96, height: 96, child: ClipOval(child: Portrait(name: p.firstName, url: p.photos.firstOrNull, borderRadius: 0))),
        const SizedBox(height: FmSpace.md),
        Text('You matched with ${p?.firstName ?? 'someone'}', style: context.text.headlineSmall, textAlign: TextAlign.center),
        const SizedBox(height: 6),
        Text('Break the ice with something personal.', style: context.text.bodyMedium?.copyWith(color: fm.textMuted)),
        const SizedBox(height: FmSpace.lg),
        for (final s in starters)
          Padding(
            padding: const EdgeInsets.only(bottom: 8),
            child: InkWell(
              borderRadius: BorderRadius.circular(FmRadius.md),
              onTap: () => onPick(s),
              child: Container(
                width: double.infinity,
                padding: const EdgeInsets.all(14),
                decoration: BoxDecoration(color: fm.surface, borderRadius: BorderRadius.circular(FmRadius.md), border: Border.all(color: fm.stroke)),
                child: Row(children: [
                  Icon(Icons.lightbulb_outline_rounded, size: 18, color: fm.accent),
                  const SizedBox(width: 10),
                  Expanded(child: Text(s, style: context.text.bodyMedium)),
                ]),
              ),
            ),
          ),
      ]),
    );
  }
}

class _RephraseSheet extends ConsumerWidget {
  const _RephraseSheet({required this.draft});
  final String draft;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(FmSpace.lg, 0, FmSpace.lg, FmSpace.lg),
        child: FutureBuilder<List<String>>(
          future: ref.read(repoProvider).aiRephrase(draft),
          builder: (ctx, snap) {
            if (snap.hasError) return MessageState.error(snap.error!);
            if (!snap.hasData) {
              return const SizedBox(height: 180, child: Center(child: CircularProgressIndicator()));
            }
            return Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text('Suggestions', style: context.text.headlineSmall),
              Text('Only your draft is sent to the AI — never your conversation.', style: context.text.bodySmall),
              const SizedBox(height: FmSpace.md),
              for (final s in snap.data!)
                ListTile(
                  contentPadding: EdgeInsets.zero,
                  leading: const Icon(Icons.auto_awesome),
                  title: Text(s),
                  onTap: () => Navigator.pop(context, s),
                ),
            ]);
          },
        ),
      ),
    );
  }
}
