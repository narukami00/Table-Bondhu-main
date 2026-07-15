import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:path_provider/path_provider.dart';
import 'package:record/record.dart';

void main() {
  runApp(const TableBondhuApp());
}

class TableBondhuApp extends StatelessWidget {
  const TableBondhuApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Table-Bondhu',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        useMaterial3: true,
        brightness: Brightness.dark,
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(0xFFFEE000), // Pikachu Yellow
          brightness: Brightness.dark,
          primary: const Color(0xFFFEE000),
          secondary: const Color(0xFFFFB300),
        ),
        scaffoldBackgroundColor: const Color(0xFF121212),
        cardColor: const Color(0xFF1E1E1E),
      ),
      home: const MainNavigationScreen(),
    );
  }
}

class MainNavigationScreen extends StatefulWidget {
  const MainNavigationScreen({super.key});

  @override
  State<MainNavigationScreen> createState() => _MainNavigationScreenState();
}

class _MainNavigationScreenState extends State<MainNavigationScreen> {
  int _selectedIndex = 0;
  String _serverIp = "10.93.229.20"; // Default server IP
  bool _isConnected = false;
  Timer? _pingTimer;
  RawDatagramSocket? _udpSocket;
  StreamSubscription? _udpSubscription;
  bool _isUdpActive = false;

  @override
  void initState() {
    super.initState();
    _initConnectionManager();
  }

  void _initConnectionManager() async {
    // 1. Load saved IP
    final savedIp = await _loadIp();
    setState(() {
      _serverIp = savedIp;
    });

    // 2. Ping once
    await _checkConnection();

    // 3. Start periodic ping checks (every 4 seconds)
    _pingTimer = Timer.periodic(const Duration(seconds: 4), (timer) {
      _checkConnection();
    });
  }

  Future<void> _checkConnection() async {
    try {
      final response = await http.get(
        Uri.parse('http://$_serverIp:8888/api/ping'),
      ).timeout(const Duration(seconds: 2));

      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        if (data['status'] == 'OK') {
          if (!_isConnected) {
            setState(() {
              _isConnected = true;
            });
            _stopUdpSearch();
          }
          return;
        }
      }
    } catch (_) {}

    // If we reach here, connection check failed
    if (_isConnected) {
      setState(() {
        _isConnected = false;
      });
    }
    // Start background auto-discovery if disconnected
    _startUdpSearch();
  }

  void _startUdpSearch() async {
    if (_isUdpActive) return;
    _isUdpActive = true;

    try {
      _udpSocket = await RawDatagramSocket.bind(InternetAddress.anyIPv4, 9999);
      _udpSocket!.broadcastEnabled = true;

      _udpSubscription = _udpSocket!.listen((RawSocketEvent event) {
        if (event == RawSocketEvent.read) {
          Datagram? dg = _udpSocket!.receive();
          if (dg != null) {
            String message = utf8.decode(dg.data).trim();
            if (message.contains("TABLE_BONDHU_BEACON")) {
              final discoveredIp = dg.address.address;
              _onIpConfigured(discoveredIp);
              _stopUdpSearch();
              _checkConnection(); // Ping immediately
            }
          }
        }
      });
    } catch (_) {
      _isUdpActive = false;
    }
  }

  void _stopUdpSearch() {
    _udpSubscription?.cancel();
    _udpSocket?.close();
    _isUdpActive = false;
  }

  Future<File> _getIpFile() async {
    final tempDir = await getTemporaryDirectory();
    return File('${tempDir.path}/saved_server_ip.txt');
  }

  Future<void> _saveIp(String ip) async {
    try {
      final file = await _getIpFile();
      await file.writeAsString(ip);
    } catch (_) {}
  }

  Future<String> _loadIp() async {
    try {
      final file = await _getIpFile();
      if (await file.exists()) {
        return await file.readAsString();
      }
    } catch (_) {}
    return "10.93.229.20"; // Default fallback
  }

  void _onIpConfigured(String newIp) {
    if (_serverIp != newIp) {
      setState(() {
        _serverIp = newIp;
      });
      _saveIp(newIp);
      _checkConnection(); // Ping immediately
    }
  }

  @override
  void dispose() {
    _pingTimer?.cancel();
    _stopUdpSearch();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final List<Widget> screens = [
      ConnectionScreen(
        initialServerIp: _serverIp,
        onIpConfigured: _onIpConfigured,
        isConnected: _isConnected,
      ),
      ChatScreen(serverIp: _serverIp),
      RemindersScreen(serverIp: _serverIp),
      TimerScreen(serverIp: _serverIp),
      SleepScreen(serverIp: _serverIp),
    ];

    return Scaffold(
      body: SafeArea(child: screens[_selectedIndex]),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _selectedIndex,
        onDestinationSelected: (index) {
          if (index != 0 && !_isConnected) {
            // Lock tabs if not connected!
            ScaffoldMessenger.of(context).showSnackBar(
              const SnackBar(
                content: Text('Cannot access features: Disconnected from Table-Bondhu Companion Server.'),
                duration: Duration(seconds: 2),
                backgroundColor: Colors.redAccent,
              ),
            );
            return;
          }
          setState(() {
            _selectedIndex = index;
          });
        },
        destinations: const [
          NavigationDestination(
            icon: Icon(Icons.wifi_find),
            label: 'Connection',
          ),
          NavigationDestination(
            icon: Icon(Icons.chat_bubble_outline),
            label: 'Chat',
          ),
          NavigationDestination(
            icon: Icon(Icons.alarm),
            label: 'Reminders',
          ),
          NavigationDestination(
            icon: Icon(Icons.hourglass_empty),
            label: 'Timer',
          ),
          NavigationDestination(
            icon: Icon(Icons.bedtime),
            label: 'Sleep Logs',
          ),
        ],
      ),
    );
  }
}

// ==========================================
// 1. CONNECTION SCREEN
// ==========================================
class ConnectionScreen extends StatefulWidget {
  final String initialServerIp;
  final ValueChanged<String> onIpConfigured;
  final bool isConnected;

  const ConnectionScreen({
    super.key,
    required this.initialServerIp,
    required this.onIpConfigured,
    required this.isConnected,
  });

  @override
  State<ConnectionScreen> createState() => _ConnectionScreenState();
}

class _ConnectionScreenState extends State<ConnectionScreen> {
  late TextEditingController _ssidController;
  late TextEditingController _passwordController;
  late TextEditingController _serverIpController;

  bool _isProvisioning = false;
  String _provisioningLog = "";

  @override
  void initState() {
    super.initState();
    _ssidController = TextEditingController(text: "Rafsan's S21");
    _passwordController = TextEditingController(text: "12345678");
    _serverIpController = TextEditingController(text: widget.initialServerIp);
  }

  @override
  void didUpdateWidget(covariant ConnectionScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.initialServerIp != widget.initialServerIp) {
      _serverIpController.text = widget.initialServerIp;
    }
  }

  @override
  void dispose() {
    _ssidController.dispose();
    _passwordController.dispose();
    _serverIpController.dispose();
    super.dispose();
  }

  void _log(String message) {
    if (mounted) {
      setState(() {
        _provisioningLog += "[${DateTime.now().toString().substring(11, 19)}] $message\n";
      });
    }
  }

  void _sendConfiguration() async {
    final ssid = _ssidController.text.trim();
    final password = _passwordController.text.trim();
    final ip = _serverIpController.text.trim();

    if (ssid.isEmpty || password.isEmpty || ip.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Please fill all configuration fields.')),
      );
      return;
    }

    setState(() {
      _isProvisioning = true;
    });
    _log("Sending configuration to ESP32 (http://192.168.4.1/setup)...");

    try {
      final response = await http.post(
        Uri.parse('http://192.168.4.1/setup'),
        body: {
          'ssid': ssid,
          'password': password,
          'server_ip': ip,
        },
      ).timeout(const Duration(seconds: 8));

      if (response.statusCode == 200) {
        _log("Success: ESP32 received configuration!");
        widget.onIpConfigured(ip);
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Provisioning successful! ESP32 restarting...')),
          );
        }
      } else {
        _log("Error: Server responded with status code ${response.statusCode}");
      }
    } catch (e) {
      _log("Connection failed: Is your phone connected to 'Table-Bondhu-Config'?");
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Failed to connect to ESP32 Access Point.')),
        );
      }
    } finally {
      if (mounted) {
        setState(() {
          _isProvisioning = false;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Connection Setup'),
        centerTitle: true,
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // Status bar at the top
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: widget.isConnected ? Colors.green.withValues(alpha: 0.15) : Colors.redAccent.withValues(alpha: 0.15),
                borderRadius: BorderRadius.circular(8),
                border: Border.all(
                  color: widget.isConnected ? Colors.green : Colors.redAccent,
                  width: 1.5,
                ),
              ),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(
                    widget.isConnected ? Icons.check_circle : Icons.error_outline,
                    color: widget.isConnected ? Colors.green : Colors.redAccent,
                  ),
                  const SizedBox(width: 8),
                  Text(
                    widget.isConnected
                        ? 'Connected to Pikachu Server (${widget.initialServerIp})'
                        : 'Searching Server IP on Network...',
                    style: TextStyle(
                      fontWeight: FontWeight.bold,
                      color: widget.isConnected ? Colors.green : Colors.redAccent,
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 16),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16.0),
                child: Column(
                  children: [
                    !widget.isConnected
                        ? const PikaSearchAnimation(size: 100)
                        : Image.asset(
                            'assets/Pikachu/eyes_open_mouth_closed.png',
                            width: 100,
                            height: 100,
                            errorBuilder: (c, e, s) => const Icon(Icons.settings_input_antenna, size: 48, color: Color(0xFFFEE000)),
                          ),
                    const SizedBox(height: 12),
                    const Text(
                      'Connection Manager',
                      style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                    ),
                    const SizedBox(height: 8),
                    Text(
                      !widget.isConnected ? 'Auto-scanning for local UDP beacons...' : 'You are linked. Features are unlocked!',
                      textAlign: TextAlign.center,
                      style: const TextStyle(color: Colors.grey),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 16),
            TextField(
              controller: _ssidController,
              decoration: const InputDecoration(
                labelText: 'Target WiFi SSID',
                border: OutlineInputBorder(),
                prefixIcon: Icon(Icons.wifi),
              ),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _passwordController,
              obscureText: true,
              decoration: const InputDecoration(
                labelText: 'WiFi Password',
                border: OutlineInputBorder(),
                prefixIcon: Icon(Icons.lock),
              ),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _serverIpController,
              onChanged: (val) => widget.onIpConfigured(val.trim()),
              decoration: const InputDecoration(
                labelText: 'Python Server IP',
                border: OutlineInputBorder(),
                prefixIcon: Icon(Icons.computer),
              ),
            ),
            const SizedBox(height: 20),
            ElevatedButton(
              onPressed: _isProvisioning ? null : _sendConfiguration,
              style: ElevatedButton.styleFrom(
                backgroundColor: const Color(0xFFFEE000),
                foregroundColor: Colors.black,
                padding: const EdgeInsets.symmetric(vertical: 16),
              ),
              child: _isProvisioning
                  ? const CircularProgressIndicator(color: Colors.black)
                  : const Text('Provision ESP32 Device', style: TextStyle(fontWeight: FontWeight.bold)),
            ),
            const SizedBox(height: 24),
            const Text(
              'Activity Log',
              style: TextStyle(fontWeight: FontWeight.bold, color: Colors.grey),
            ),
            const SizedBox(height: 8),
            Container(
              height: 120,
              padding: const EdgeInsets.all(8),
              decoration: BoxDecoration(
                color: Colors.black45,
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: Colors.white10),
              ),
              child: SingleChildScrollView(
                reverse: true,
                child: Text(
                  _provisioningLog.isEmpty ? "Waiting for activity..." : _provisioningLog,
                  style: const TextStyle(fontFamily: 'monospace', fontSize: 11, color: Colors.green),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

// ==========================================
// 2. CHAT SCREEN
// ==========================================
class ChatMessage {
  final String text;
  final bool isUser;
  final DateTime timestamp;

  ChatMessage({required this.text, required this.isUser, required this.timestamp});
}

class ChatScreen extends StatefulWidget {
  final String serverIp;

  const ChatScreen({super.key, required this.serverIp});

  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends State<ChatScreen> {
  final List<ChatMessage> _messages = [];
  final _messageController = TextEditingController();
  bool _isLoading = false;

  // Recording API
  final _audioRecorder = AudioRecorder();
  bool _isRecording = false;
  String _recordingStatus = "";
  DateTime _recordingStartTime = DateTime.now();

  @override
  void initState() {
    super.initState();
    _messages.add(ChatMessage(
      text: "Hello! I am Table-Bondhu. How can I help you today?",
      isUser: false,
      timestamp: DateTime.now(),
    ));
  }

  @override
  void dispose() {
    _audioRecorder.dispose();
    _messageController.dispose();
    super.dispose();
  }

  void _sendMessage() async {
    final text = _messageController.text.trim();
    if (text.isEmpty) return;

    _messageController.clear();
    setState(() {
      _messages.add(ChatMessage(text: text, isUser: true, timestamp: DateTime.now()));
      _isLoading = true;
    });

    try {
      final response = await http.post(
        Uri.parse('http://${widget.serverIp}:8888/api/chat'),
        headers: {'Content-Type': 'application/json'},
        body: json.encode({'message': text}),
      ).timeout(const Duration(seconds: 15));

      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        final reply = data['response'] ?? "No response received.";
        setState(() {
          _messages.add(ChatMessage(text: reply, isUser: false, timestamp: DateTime.now()));
        });
      } else {
        setState(() {
          _messages.add(ChatMessage(
            text: "Error: Server returned status code ${response.statusCode}",
            isUser: false,
            timestamp: DateTime.now(),
          ));
        });
      }
    } catch (e) {
      setState(() {
        _messages.add(ChatMessage(
          text: "Connection failed: Please verify that the companion server is running at ${widget.serverIp}:8888",
          isUser: false,
          timestamp: DateTime.now(),
        ));
      });
    } finally {
      if (mounted) {
        setState(() {
          _isLoading = false;
        });
      }
    }
  }

  // --- Voice Message Recording ---
  void _startRecording() async {
    try {
      if (await _audioRecorder.hasPermission()) {
        final tempDir = await getTemporaryDirectory();
        final path = '${tempDir.path}/voice_chat.wav';

        final prevFile = File(path);
        if (await prevFile.exists()) {
          await prevFile.delete();
        }

        _recordingStartTime = DateTime.now();

        await _audioRecorder.start(
          const RecordConfig(
            encoder: AudioEncoder.wav,
            sampleRate: 16000,
            numChannels: 1,
          ),
          path: path,
        );

        setState(() {
          _isRecording = true;
          _recordingStatus = "Listening... Release button to send.";
        });
      } else {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Audio Recording Permission Denied.')),
          );
        }
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Failed to start recording: $e')),
        );
      }
    }
  }

  void _stopRecordingAndSend() async {
    if (!_isRecording) return;
    
    final holdDuration = DateTime.now().difference(_recordingStartTime);
    if (holdDuration.inMilliseconds < 800) {
      // Discard tap/short hold
      setState(() {
        _isRecording = false;
        _recordingStatus = "";
      });
      try {
        await _audioRecorder.stop();
      } catch (_) {}
      
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Hold to talk, release to send (tap is too short).'),
            duration: Duration(milliseconds: 1500),
          ),
        );
      }
      return;
    }

    setState(() {
      _isRecording = false;
      _recordingStatus = "";
      _isLoading = true;
    });

    try {
      final path = await _audioRecorder.stop();
      if (path != null) {
        final file = File(path);
        if (await file.exists()) {
          final bytes = await file.readAsBytes();
          final base64Audio = base64Encode(bytes);

          setState(() {
            _messages.add(ChatMessage(text: "[Voice Message]", isUser: true, timestamp: DateTime.now()));
          });

          final response = await http.post(
            Uri.parse('http://${widget.serverIp}:8888/api/voice_chat'),
            headers: {'Content-Type': 'application/json'},
            body: json.encode({'audio': base64Audio}),
          ).timeout(const Duration(seconds: 20));

          if (response.statusCode == 200) {
            final data = json.decode(response.body);
            final transcribedText = data['text'] ?? "";
            final reply = data['response'] ?? "No response received.";

            setState(() {
              if (_messages.isNotEmpty && _messages.last.text == "[Voice Message]") {
                _messages.removeLast();
              }
              _messages.add(ChatMessage(
                text: "Heard: \"$transcribedText\"",
                isUser: true,
                timestamp: DateTime.now(),
              ));
              _messages.add(ChatMessage(text: reply, isUser: false, timestamp: DateTime.now()));
            });
          } else {
            _showErrorBubble("Error: Voice server returned status code ${response.statusCode}");
          }
        }
      }
    } catch (e) {
      _showErrorBubble("Voice connection failed: $e");
    } finally {
      if (mounted) {
        setState(() {
          _isLoading = false;
        });
      }
    }
  }

  void _showErrorBubble(String errMsg) {
    setState(() {
      if (_messages.isNotEmpty && _messages.last.text == "[Voice Message]") {
        _messages.removeLast();
      }
      _messages.add(ChatMessage(text: errMsg, isUser: false, timestamp: DateTime.now()));
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('LLM Agent Chat'),
        centerTitle: true,
      ),
      body: Column(
        children: [
          Expanded(
            child: ListView.builder(
              padding: const EdgeInsets.all(16),
              reverse: true,
              itemCount: _messages.length,
              itemBuilder: (context, index) {
                final message = _messages[_messages.length - 1 - index];
                return _buildChatBubble(message);
              },
            ),
          ),
          if (_isLoading)
            const Padding(
              padding: EdgeInsets.symmetric(vertical: 8.0),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  PikaSpeakingAnimation(size: 40),
                  SizedBox(width: 12),
                  Text('Pikachu is thinking...', style: TextStyle(color: Colors.grey, fontStyle: FontStyle.italic)),
                ],
              ),
            ),
          if (_isRecording)
            Container(
              padding: const EdgeInsets.all(12),
              color: Colors.redAccent.withValues(alpha: 0.15),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  const Icon(Icons.fiber_manual_record, color: Colors.redAccent, size: 16),
                  const SizedBox(width: 8),
                  Text(
                    _recordingStatus,
                    style: const TextStyle(color: Colors.redAccent, fontWeight: FontWeight.bold),
                  ),
                ],
              ),
            ),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 8.0, vertical: 6.0),
            color: Colors.black26,
            child: Row(
              children: [
                Listener(
                  onPointerDown: (_) => _startRecording(),
                  onPointerUp: (_) => _stopRecordingAndSend(),
                  child: Container(
                    padding: const EdgeInsets.all(10),
                    decoration: BoxDecoration(
                      color: _isRecording ? Colors.redAccent : Colors.white10,
                      shape: BoxShape.circle,
                    ),
                    child: Icon(
                      Icons.mic,
                      color: _isRecording ? Colors.white : const Color(0xFFFEE000),
                    ),
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: TextField(
                    controller: _messageController,
                    onSubmitted: (_) => _sendMessage(),
                    decoration: const InputDecoration(
                      hintText: 'Type prompt or hold mic...',
                      border: InputBorder.none,
                      contentPadding: EdgeInsets.symmetric(horizontal: 12),
                    ),
                  ),
                ),
                IconButton(
                  icon: const Icon(Icons.send, color: Color(0xFFFEE000)),
                  onPressed: _sendMessage,
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildChatBubble(ChatMessage message) {
    final isUser = message.isUser;
    return Align(
      alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.symmetric(vertical: 6),
        child: Row(
          mainAxisAlignment: isUser ? MainAxisAlignment.end : MainAxisAlignment.start,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (!isUser) ...[
              CircleAvatar(
                radius: 18,
                backgroundColor: Colors.white10,
                child: Image.asset(
                  'assets/Pikachu/eyes_open_mouth_closed.png',
                  width: 32,
                  height: 32,
                  errorBuilder: (c, e, s) => const Icon(Icons.face, color: Color(0xFFFEE000)),
                ),
              ),
              const SizedBox(width: 8),
            ],
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
              constraints: BoxConstraints(maxWidth: MediaQuery.of(context).size.width * 0.65),
              decoration: BoxDecoration(
                color: isUser ? const Color(0xFFFEE000) : const Color(0xFF2C2C2C),
                borderRadius: BorderRadius.only(
                  topLeft: const Radius.circular(12),
                  topRight: const Radius.circular(12),
                  bottomLeft: Radius.circular(isUser ? 12 : 0),
                  bottomRight: Radius.circular(isUser ? 0 : 12),
                ),
              ),
              child: Text(
                message.text,
                style: TextStyle(
                  color: isUser ? Colors.black : Colors.white,
                  fontSize: 15,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

// ==========================================
// 3. REMINDERS SCREEN
// ==========================================
class RemindersScreen extends StatefulWidget {
  final String serverIp;

  const RemindersScreen({super.key, required this.serverIp});

  @override
  State<RemindersScreen> createState() => _RemindersScreenState();
}

class _RemindersScreenState extends State<RemindersScreen> {
  List<dynamic> _reminders = [];
  bool _isLoading = false;

  @override
  void initState() {
    super.initState();
    _fetchReminders();
  }

  Future<void> _fetchReminders() async {
    if (!mounted) return;
    setState(() {
      _isLoading = true;
    });

    try {
      final response = await http.get(
        Uri.parse('http://${widget.serverIp}:8888/api/reminders'),
      ).timeout(const Duration(seconds: 5));

      if (response.statusCode == 200) {
        setState(() {
          _reminders = json.decode(response.body);
        });
      }
    } catch (e) {
      // Fail silently
    } finally {
      if (mounted) {
        setState(() {
          _isLoading = false;
        });
      }
    }
  }

  void _addReminder(String task, String dateTimeStr) async {
    try {
      final response = await http.post(
        Uri.parse('http://${widget.serverIp}:8888/api/reminders'),
        headers: {'Content-Type': 'application/json'},
        body: json.encode({'task': task, 'time': dateTimeStr}),
      ).timeout(const Duration(seconds: 5));

      if (response.statusCode == 200) {
        _fetchReminders();
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Failed to add reminder.')),
        );
      }
    }
  }

  void _deleteReminder(int index) async {
    try {
      final response = await http.post(
        Uri.parse('http://${widget.serverIp}:8888/api/reminders/delete'),
        headers: {'Content-Type': 'application/json'},
        body: json.encode({'index': index}),
      ).timeout(const Duration(seconds: 5));

      if (response.statusCode == 200) {
        _fetchReminders();
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Failed to delete reminder.')),
        );
      }
    }
  }

  void _clearReminders() async {
    try {
      final response = await http.post(
        Uri.parse('http://${widget.serverIp}:8888/api/reminders/clear'),
      ).timeout(const Duration(seconds: 5));

      if (response.statusCode == 200) {
        _fetchReminders();
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Failed to clear reminders.')),
        );
      }
    }
  }

  void _showAddDialog() {
    final taskController = TextEditingController();
    final dateController = TextEditingController(text: DateTime.now().toString().substring(0, 10));
    final timeController = TextEditingController(text: "12:00:00");

    showDialog(
      context: context,
      builder: (context) {
        return AlertDialog(
          title: const Text('New Reminder'),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextField(
                controller: taskController,
                decoration: const InputDecoration(labelText: 'Task / Alarm Description'),
              ),
              TextField(
                controller: dateController,
                decoration: const InputDecoration(labelText: 'Date (YYYY-MM-DD)'),
              ),
              TextField(
                controller: timeController,
                decoration: const InputDecoration(labelText: 'Time (HH:MM:SS)'),
              ),
            ],
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('Cancel'),
            ),
            TextButton(
              onPressed: () {
                final task = taskController.text.trim();
                final fullTime = "${dateController.text.trim()} ${timeController.text.trim()}";
                if (task.isNotEmpty) {
                  _addReminder(task, fullTime);
                  Navigator.pop(context);
                }
              },
              child: const Text('Create'),
            ),
          ],
        );
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Reminders & Alarms'),
        centerTitle: true,
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: _fetchReminders,
          ),
          IconButton(
            icon: const Icon(Icons.delete_sweep, color: Colors.redAccent),
            onPressed: _clearReminders,
            tooltip: 'Clear All',
          ),
        ],
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : _reminders.isEmpty
              ? Center(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Image.asset(
                        'assets/Pikachu/eyes_half_smile.png',
                        width: 100,
                        height: 100,
                        errorBuilder: (c, e, s) => const Icon(Icons.alarm_off, size: 64, color: Colors.grey),
                      ),
                      const SizedBox(height: 12),
                      const Text('No alarms or reminders found.', style: TextStyle(color: Colors.grey)),
                    ],
                  ),
                )
              : ListView.builder(
                  padding: const EdgeInsets.all(16),
                  itemCount: _reminders.length,
                  itemBuilder: (context, index) {
                    final item = _reminders[index];
                    final isFired = item['fired'] == true;
                    return Card(
                      margin: const EdgeInsets.only(bottom: 12),
                      child: ListTile(
                        leading: CircleAvatar(
                          backgroundColor: Colors.white10,
                          child: Icon(
                            isFired ? Icons.alarm_on : Icons.alarm,
                            color: isFired ? Colors.redAccent : const Color(0xFFFEE000),
                          ),
                        ),
                        title: Text(
                          item['task'] ?? "Reminder",
                          style: const TextStyle(fontWeight: FontWeight.bold),
                        ),
                        subtitle: Text(
                          "Time: ${item['display_time'] ?? item['trigger_time']}",
                          style: const TextStyle(color: Colors.grey),
                        ),
                        trailing: IconButton(
                          icon: const Icon(Icons.delete, color: Colors.grey),
                          onPressed: () => _deleteReminder(index + 1), // API expects 1-based index
                        ),
                      ),
                    );
                  },
                ),
      floatingActionButton: FloatingActionButton(
        onPressed: _showAddDialog,
        backgroundColor: const Color(0xFFFEE000),
        foregroundColor: Colors.black,
        child: const Icon(Icons.add),
      ),
    );
  }
}

// ==========================================
// 4. FOCUS TIMER
// ==========================================
class TimerScreen extends StatefulWidget {
  final String serverIp;

  const TimerScreen({super.key, required this.serverIp});

  @override
  State<TimerScreen> createState() => _TimerScreenState();
}

class _TimerScreenState extends State<TimerScreen> {
  int _selectedDuration = 1500; // Default 25 minutes
  Timer? _timer;
  int _secondsLeft = 0;
  bool _isRunning = false;

  void _startTimer(int seconds) async {
    try {
      final response = await http.post(
        Uri.parse('http://${widget.serverIp}:8888/api/timer/start'),
        headers: {'Content-Type': 'application/json'},
        body: json.encode({'duration': seconds}),
      ).timeout(const Duration(seconds: 5));

      if (response.statusCode == 200) {
        _timer?.cancel();
        setState(() {
          _secondsLeft = seconds;
          _isRunning = true;
        });
        _timer = Timer.periodic(const Duration(seconds: 1), (timer) {
          if (mounted) {
            setState(() {
              if (_secondsLeft > 0) {
                _secondsLeft--;
              } else {
                _isRunning = false;
                _timer?.cancel();
              }
            });
          }
        });
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Failed to start focus timer.')),
        );
      }
    }
  }

  void _cancelTimer() async {
    try {
      final response = await http.post(
        Uri.parse('http://${widget.serverIp}:8888/api/timer/cancel'),
      ).timeout(const Duration(seconds: 5));

      if (response.statusCode == 200) {
        _timer?.cancel();
        setState(() {
          _isRunning = false;
          _secondsLeft = 0;
        });
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Failed to cancel focus timer.')),
        );
      }
    }
  }

  String _formatDuration(int totalSeconds) {
    final m = totalSeconds ~/ 60;
    final s = totalSeconds % 60;
    final mStr = m.toString().padLeft(2, '0');
    final sStr = s.toString().padLeft(2, '0');
    return "$mStr:$sStr";
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Focus Timer Controller'),
        centerTitle: true,
      ),
      body: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Stack(
              alignment: Alignment.center,
              children: [
                SizedBox(
                  width: 240,
                  height: 240,
                  child: CircularProgressIndicator(
                    value: _isRunning && _selectedDuration > 0
                        ? _secondsLeft / _selectedDuration
                        : 0.0,
                    strokeWidth: 12,
                    backgroundColor: Colors.white10,
                    color: const Color(0xFFFEE000),
                  ),
                ),
                Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    _isRunning
                        ? const PikaWavingAnimation(size: 70)
                        : Image.asset(
                            'assets/Pikachu/eyes_open_mouth_closed.png',
                            width: 70,
                            height: 70,
                            errorBuilder: (c, e, s) => const SizedBox(height: 70),
                          ),
                    const SizedBox(height: 6),
                    Text(
                      _isRunning ? _formatDuration(_secondsLeft) : "00:00",
                      style: const TextStyle(fontSize: 36, fontWeight: FontWeight.bold),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      _isRunning ? 'Focusing...' : 'Ready',
                      style: TextStyle(color: Colors.grey.shade400, fontWeight: FontWeight.w500),
                    ),
                  ],
                ),
              ],
            ),
            const SizedBox(height: 48),
            if (!_isRunning) ...[
              const Text('Select Focus Duration:', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
              const SizedBox(height: 16),
              Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  _durationButton(10, '10s (Test)'),
                  const SizedBox(width: 8),
                  _durationButton(300, '5m'),
                  const SizedBox(width: 8),
                  _durationButton(1500, '25m'),
                  const SizedBox(width: 8),
                  _durationButton(3000, '50m'),
                ],
              ),
              const SizedBox(height: 24),
              ElevatedButton.icon(
                onPressed: () => _startTimer(_selectedDuration),
                icon: const Icon(Icons.play_arrow),
                label: const Text('Start Focus Session', style: TextStyle(fontWeight: FontWeight.bold)),
                style: ElevatedButton.styleFrom(
                  backgroundColor: const Color(0xFFFEE000),
                  foregroundColor: Colors.black,
                  padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
                ),
              ),
            ] else ...[
              ElevatedButton.icon(
                onPressed: _cancelTimer,
                icon: const Icon(Icons.stop),
                label: const Text('Cancel Timer', style: TextStyle(fontWeight: FontWeight.bold)),
                style: ElevatedButton.styleFrom(
                  backgroundColor: Colors.redAccent,
                  foregroundColor: Colors.white,
                  padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _durationButton(int seconds, String label) {
    final isSelected = _selectedDuration == seconds;
    return ChoiceChip(
      label: Text(label),
      selected: isSelected,
      onSelected: (selected) {
        if (selected) {
          setState(() {
            _selectedDuration = seconds;
          });
        }
      },
    );
  }
}

// ==========================================
// 5. SLEEP LOGS SCREEN
// ==========================================
class SleepScreen extends StatefulWidget {
  final String serverIp;

  const SleepScreen({super.key, required this.serverIp});

  @override
  State<SleepScreen> createState() => _SleepScreenState();
}

class _SleepScreenState extends State<SleepScreen>
    with SingleTickerProviderStateMixin {
  List<dynamic> _sessions = [];
  bool _isLoading = false;
  String _scheduledTime = "Not Set";

  // Active sleep state
  bool _isSleeping = false;
  DateTime? _sleepStartTime;
  Timer? _elapsedTimer;
  String _elapsedStr = "00:00:00";

  // Last wake summary
  Map<String, dynamic>? _lastWakeSummary;

  // Sleep window ("away from home" protection)
  int _windowStart = 22; // 10 PM default
  int _windowEnd   = 10; // 10 AM default

  late AnimationController _pulseCtrl;
  late Animation<double> _pulseAnim;

  @override
  void initState() {
    super.initState();
    _pulseCtrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1500),
    )..repeat(reverse: true);
    _pulseAnim = Tween<double>(begin: 0.95, end: 1.05).animate(
      CurvedAnimation(parent: _pulseCtrl, curve: Curves.easeInOut),
    );
    _fetchSleepStatus();
    _fetchSleepLogs();
    _fetchScheduledTime();
    _fetchSleepWindow();
  }

  @override
  void dispose() {
    _elapsedTimer?.cancel();
    _pulseCtrl.dispose();
    super.dispose();
  }

  // ---- Elapsed timer ----
  void _startElapsedTimer() {
    _elapsedTimer?.cancel();
    _elapsedTimer = Timer.periodic(const Duration(seconds: 1), (_) {
      if (!mounted || _sleepStartTime == null) return;
      final elapsed = DateTime.now().difference(_sleepStartTime!);
      setState(() {
        final h = elapsed.inHours.toString().padLeft(2, '0');
        final m = (elapsed.inMinutes % 60).toString().padLeft(2, '0');
        final s = (elapsed.inSeconds % 60).toString().padLeft(2, '0');
        _elapsedStr = "$h:$m:$s";
      });
    });
  }

  // ---- Fetch persisted sleep status from server ----
  Future<void> _fetchSleepStatus() async {
    try {
      final response = await http.get(
        Uri.parse('http://${widget.serverIp}:8888/api/sleep/status'),
      ).timeout(const Duration(seconds: 5));

      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        final isSleeping = data['is_sleeping'] == true;
        DateTime? startTime;
        if (data['start_time'] != null) {
          try {
            startTime = DateTime.parse(data['start_time'].toString());
          } catch (_) {
            // start_time may be a unix timestamp
            try {
              startTime = DateTime.fromMillisecondsSinceEpoch(
                  (data['start_time'] as num).toInt() * 1000);
            } catch (_) {}
          }
        }
        if (mounted) {
          setState(() {
            _isSleeping = isSleeping;
            _sleepStartTime = startTime;
          });
          if (isSleeping) {
            _startElapsedTimer();
          }
        }
      }
    } catch (_) {}
  }

  Future<void> _fetchSleepLogs() async {
    if (!mounted) return;
    setState(() => _isLoading = true);
    try {
      final response = await http.get(
        Uri.parse('http://${widget.serverIp}:8888/api/sleep'),
      ).timeout(const Duration(seconds: 5));
      if (response.statusCode == 200) {
        setState(() => _sessions = json.decode(response.body));
      }
    } catch (_) {
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  Future<void> _fetchScheduledTime() async {
    try {
      final response = await http.get(
        Uri.parse('http://${widget.serverIp}:8888/api/sleep/schedule'),
      ).timeout(const Duration(seconds: 5));
      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        final timeStr = data['scheduled_time'];
        if (timeStr != null && timeStr.toString().isNotEmpty && mounted) {
          setState(() => _scheduledTime = _formatTimeStr(timeStr.toString()));
        }
      }
    } catch (_) {}
  }

  // ---- Sleep Window ----
  Future<void> _fetchSleepWindow() async {
    try {
      final response = await http.get(
        Uri.parse('http://${widget.serverIp}:8888/api/sleep/window'),
      ).timeout(const Duration(seconds: 5));
      if (response.statusCode == 200 && mounted) {
        final data = json.decode(response.body);
        setState(() {
          _windowStart = (data['start_hour'] as num?)?.toInt() ?? 22;
          _windowEnd   = (data['end_hour']   as num?)?.toInt() ?? 10;
        });
      }
    } catch (_) {}
  }

  Future<void> _saveSleepWindow(int start, int end) async {
    try {
      final response = await http.post(
        Uri.parse('http://${widget.serverIp}:8888/api/sleep/window'),
        headers: {'Content-Type': 'application/json'},
        body: json.encode({'start_hour': start, 'end_hour': end}),
      ).timeout(const Duration(seconds: 5));
      if (response.statusCode == 200 && mounted) {
        setState(() {
          _windowStart = start;
          _windowEnd   = end;
        });
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              'Sleep window set: ${_fmtHour(start)} → ${_fmtHour(end)}',
            ),
          ),
        );
      }
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Failed to update sleep window.')),
        );
      }
    }
  }

  String _fmtHour(int h) {
    final suffix = h >= 12 ? 'PM' : 'AM';
    final display = h > 12 ? h - 12 : (h == 0 ? 12 : h);
    return '$display:00 $suffix';
  }

  void _pickSleepWindow() async {
    // Pick start first, then end
    final startPicked = await showTimePicker(
      context: context,
      initialTime: TimeOfDay(hour: _windowStart, minute: 0),
      helpText: 'Auto-sleep STARTS at (e.g. 10 PM)',
    );
    if (startPicked == null || !mounted) return;

    final endPicked = await showTimePicker(
      context: context,
      initialTime: TimeOfDay(hour: _windowEnd, minute: 0),
      helpText: 'Auto-sleep ENDS at (e.g. 10 AM)',
    );
    if (endPicked == null || !mounted) return;

    await _saveSleepWindow(startPicked.hour, endPicked.hour);
  }

  String _formatTimeStr(String militaryTime) {

    try {
      final parts = militaryTime.split(":");
      final h = int.parse(parts[0]);
      final m = int.parse(parts[1]);
      final suffix = h >= 12 ? "PM" : "AM";
      final displayH = h > 12 ? h - 12 : (h == 0 ? 12 : h);
      return "$displayH:${m.toString().padLeft(2, '0')} $suffix";
    } catch (_) {
      return militaryTime;
    }
  }

  // ---- Manual Sleep Start ----
  void _triggerInstantSleep(String type) async {
    try {
      final response = await http.post(
        Uri.parse('http://${widget.serverIp}:8888/api/sleep/start'),
        headers: {'Content-Type': 'application/json'},
        body: json.encode({'type': type}),
      ).timeout(const Duration(seconds: 5));

      if (response.statusCode == 200) {
        setState(() {
          _isSleeping = true;
          _sleepStartTime = DateTime.now();
          _lastWakeSummary = null;
        });
        _startElapsedTimer();
      } else {
        final errorMsg = json.decode(response.body)['error'] ?? "Unknown error";
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text(errorMsg), backgroundColor: Colors.redAccent),
          );
        }
      }
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Failed to connect to companion server.')),
        );
      }
    }
  }

  // ---- Manual Wake Up ----
  void _triggerManualWake() async {
    try {
      final response = await http.post(
        Uri.parse('http://${widget.serverIp}:8888/api/sleep/wake'),
        headers: {'Content-Type': 'application/json'},
        body: json.encode({}),
      ).timeout(const Duration(seconds: 8));

      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        final session = data['session'] as Map<String, dynamic>?;
        _elapsedTimer?.cancel();
        setState(() {
          _isSleeping = false;
          _sleepStartTime = null;
          _elapsedStr = "00:00:00";
          _lastWakeSummary = session;
        });
        // Refresh logs
        _fetchSleepLogs();
      } else {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Wake request failed.'), backgroundColor: Colors.redAccent),
          );
        }
      }
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Failed to connect to companion server.')),
        );
      }
    }
  }

  // ---- Bedtime Picker ----
  void _selectBedtime() async {
    final TimeOfDay? picked = await showTimePicker(
      context: context,
      initialTime: const TimeOfDay(hour: 22, minute: 0),
    );
    if (picked != null) {
      final militaryTime =
          "${picked.hour.toString().padLeft(2, '0')}:${picked.minute.toString().padLeft(2, '0')}";
      try {
        final response = await http.post(
          Uri.parse('http://${widget.serverIp}:8888/api/sleep/schedule'),
          headers: {'Content-Type': 'application/json'},
          body: json.encode({'time': militaryTime}),
        ).timeout(const Duration(seconds: 5));
        if (response.statusCode == 200 && mounted) {
          setState(() => _scheduledTime = _formatTimeStr(militaryTime));
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text('Bedtime scheduled for $_scheduledTime')),
          );
        }
      } catch (_) {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Failed to save scheduled bedtime.')),
          );
        }
      }
    }
  }

  Color _getQualityColor(String quality) {
    final q = quality.toLowerCase();
    if (q.contains("good")) return Colors.green;
    if (q.contains("poor")) return Colors.redAccent;
    return Colors.orange;
  }

  // ============================================================
  // ACTIVE SLEEP OVERLAY — shown when _isSleeping is true
  // ============================================================
  Widget _buildActiveSleepOverlay() {
    return Container(
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [
            const Color(0xFF0A0A1A),
            const Color(0xFF0D0D2B),
          ],
        ),
      ),
      child: Column(
        children: [
          const SizedBox(height: 40),
          // Stars decorative header
          const Text(
            '✦  Sleep Mode Active  ✦',
            style: TextStyle(
              color: Color(0xFFB0B8FF),
              fontSize: 14,
              letterSpacing: 2,
              fontWeight: FontWeight.w300,
            ),
          ),
          const SizedBox(height: 32),
          // Pulsing Pikachu sleeping animation
          ScaleTransition(
            scale: _pulseAnim,
            child: const PikaSleepingAnimation(size: 140),
          ),
          const SizedBox(height: 28),
          // Elapsed time display
          Text(
            _elapsedStr,
            style: const TextStyle(
              fontSize: 40,
              fontWeight: FontWeight.bold,
              color: Colors.white,
              letterSpacing: 3,
              fontFeatures: [FontFeature.tabularFigures()],
            ),
          ),
          const SizedBox(height: 8),
          const Text(
            'Sleep in progress',
            style: TextStyle(color: Color(0xFF8888AA), fontSize: 14),
          ),
          if (_sleepStartTime != null) ...[
            const SizedBox(height: 4),
            Text(
              'Started at ${_sleepStartTime!.hour.toString().padLeft(2, '0')}:${_sleepStartTime!.minute.toString().padLeft(2, '0')}',
              style: const TextStyle(color: Color(0xFF6666AA), fontSize: 12),
            ),
          ],
          const Spacer(),
          // Wake Up button — large, prominent
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 40, vertical: 48),
            child: SizedBox(
              width: double.infinity,
              height: 60,
              child: ElevatedButton.icon(
                onPressed: _triggerManualWake,
                icon: const Icon(Icons.wb_sunny_rounded, size: 24),
                label: const Text(
                  'Wake Up',
                  style: TextStyle(
                    fontSize: 18,
                    fontWeight: FontWeight.bold,
                    letterSpacing: 1,
                  ),
                ),
                style: ElevatedButton.styleFrom(
                  backgroundColor: const Color(0xFFFEE000),
                  foregroundColor: Colors.black,
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(16),
                  ),
                  elevation: 8,
                  shadowColor: const Color(0xFFFEE000).withValues(alpha: 0.4),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  // ============================================================
  // WAKE SUMMARY CARD — shown right after manual wake-up
  // ============================================================
  Widget _buildWakeSummaryCard(Map<String, dynamic> summary) {
    final durationH = summary['duration_hours'] ?? 0.0;
    final type = summary['type'] ?? "nap";
    final quality = summary['quality'] ?? "Fair";
    final movements = summary['movement_count'] ?? 0;
    final avgNoise = summary['average_noise'] ?? 0.0;
    final avgLdr = summary['average_ldr'] ?? 0.0;
    final typeName = type == "actual_sleep" ? "Sleep" : "Nap";
    final qualityColor = _getQualityColor(quality);

    return Card(
      margin: const EdgeInsets.all(16),
      color: const Color(0xFF1A1A2E),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(16),
        side: BorderSide(color: const Color(0xFFFEE000).withValues(alpha: 0.3), width: 1),
      ),
      child: Padding(
        padding: const EdgeInsets.all(20.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.center,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                const Icon(Icons.wb_sunny_rounded, color: Color(0xFFFEE000), size: 20),
                const SizedBox(width: 8),
                const Text(
                  'Last Session Summary',
                  style: TextStyle(
                    fontWeight: FontWeight.bold,
                    fontSize: 16,
                    color: Color(0xFFFEE000),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 16),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceAround,
              children: [
                _statBox('${durationH}h', typeName),
                _statBox('$movements', 'Tosses'),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                  decoration: BoxDecoration(
                    color: qualityColor.withValues(alpha: 0.15),
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: qualityColor),
                  ),
                  child: Text(
                    quality.toString().toUpperCase(),
                    style: TextStyle(
                      fontWeight: FontWeight.bold,
                      fontSize: 12,
                      color: qualityColor,
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            Text(
              'Avg Noise: ${avgNoise.toStringAsFixed(0)} RMS   |   Avg Light: ${avgLdr.toStringAsFixed(0)}',
              style: const TextStyle(color: Colors.grey, fontSize: 11),
              textAlign: TextAlign.center,
            ),
          ],
        ),
      ),
    );
  }

  // ============================================================
  // NORMAL (AWAKE) SLEEP CONTROL PANEL
  // ============================================================
  Widget _buildSleepControlPanel() {
    return Card(
      margin: const EdgeInsets.all(16),
      color: const Color(0xFF1E1E1E),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text('Target Bedtime',
                        style: TextStyle(color: Colors.grey, fontSize: 13)),
                    const SizedBox(height: 4),
                    Text(
                      _scheduledTime,
                      style: const TextStyle(
                          fontSize: 20,
                          fontWeight: FontWeight.bold,
                          color: Color(0xFFFEE000)),
                    ),
                  ],
                ),
                const PikaSleepingAnimation(size: 80),
                ElevatedButton.icon(
                  onPressed: _selectBedtime,
                  icon: const Icon(Icons.access_time),
                  label: const Text('Schedule'),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: Colors.white10,
                    foregroundColor: Colors.white,
                  ),
                ),
              ],
            ),
            const Divider(height: 16, color: Colors.white10),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text('Auto-Sleep Detection Window',
                        style: TextStyle(color: Colors.grey, fontSize: 12)),
                    const SizedBox(height: 4),
                    Text(
                      '${_fmtHour(_windowStart)} - ${_fmtHour(_windowEnd)}',
                      style: const TextStyle(
                          fontSize: 15,
                          fontWeight: FontWeight.bold,
                          color: Colors.white),
                    ),
                  ],
                ),
                ElevatedButton.icon(
                  onPressed: _pickSleepWindow,
                  icon: const Icon(Icons.tune),
                  label: const Text('Configure'),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: Colors.white10,
                    foregroundColor: Colors.white,
                    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                  ),
                ),
              ],
            ),
            const Divider(height: 24, color: Colors.white10),
            Row(
              children: [
                Expanded(
                  child: ElevatedButton.icon(
                    onPressed: () => _triggerInstantSleep("sleep"),
                    icon: const Icon(Icons.nightlight_round),
                    label: const Text('Instant Sleep',
                        style: TextStyle(fontWeight: FontWeight.bold)),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: const Color(0xFFFEE000),
                      foregroundColor: Colors.black,
                      padding: const EdgeInsets.symmetric(vertical: 12),
                    ),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: ElevatedButton.icon(
                    onPressed: () => _triggerInstantSleep("nap"),
                    icon: const Icon(Icons.wb_sunny_outlined),
                    label: const Text('Instant Nap',
                        style: TextStyle(fontWeight: FontWeight.bold)),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: Colors.white12,
                      foregroundColor: Colors.white,
                      padding: const EdgeInsets.symmetric(vertical: 12),
                    ),
                  ),
                ),
              ],
            ),
            const Divider(height: 20, color: Colors.white10),
            SizedBox(
              width: double.infinity,
              child: ElevatedButton.icon(
                onPressed: () {
                  Navigator.push(
                    context,
                    MaterialPageRoute(
                      builder: (context) => SleepAnalyticsScreen(
                        sessions: _sessions,
                        targetBedtime: _scheduledTime,
                      ),
                    ),
                  );
                },
                icon: const Icon(Icons.bar_chart_rounded),
                label: const Text('Detailed Analytics & Breakdown',
                    style: TextStyle(fontWeight: FontWeight.bold)),
                style: ElevatedButton.styleFrom(
                  backgroundColor: const Color(0xFF9333EA).withValues(alpha: 0.15),
                  foregroundColor: const Color(0xFFC084FC),
                  side: BorderSide(color: const Color(0xFF9333EA).withValues(alpha: 0.4), width: 1.5),
                  padding: const EdgeInsets.symmetric(vertical: 12),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12),
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildSleepLogCard(dynamic session) {
    final quality = session['quality'] ?? "Fair";
    final duration = session['duration_hours'] ?? 0.0;
    final type = session['type'] ?? "sleep";
    final tardiness = session['tardiness_minutes'] ?? 0;

    return Card(
      margin: const EdgeInsets.only(bottom: 16),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Row(children: [
                  Icon(
                    type.toString().toLowerCase().contains("nap")
                        ? Icons.wb_sunny
                        : Icons.nightlight_round,
                    color: const Color(0xFFFEE000),
                  ),
                  const SizedBox(width: 8),
                  Text('${type.toString().toUpperCase()} SESSION',
                      style: const TextStyle(
                          fontWeight: FontWeight.bold, fontSize: 15)),
                ]),
                Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                  decoration: BoxDecoration(
                    color: _getQualityColor(quality).withValues(alpha: 0.15),
                    borderRadius: BorderRadius.circular(12),
                    border:
                        Border.all(color: _getQualityColor(quality), width: 1),
                  ),
                  child: Text(
                    quality.toString().toUpperCase(),
                    style: TextStyle(
                        fontSize: 11,
                        fontWeight: FontWeight.bold,
                        color: _getQualityColor(quality)),
                  ),
                ),
              ],
            ),
            const Divider(height: 24, color: Colors.white12),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceAround,
              children: [
                _statBox('${duration}h', 'Duration'),
                _statBox('${session['movement_count'] ?? 0}', 'Tosses'),
                _statBox('${session['average_ldr'] ?? 0}', 'Avg Light'),
              ],
            ),
            const SizedBox(height: 16),
            if (tardiness > 0) ...[
              Container(
                margin: const EdgeInsets.only(bottom: 12),
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: Colors.redAccent.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(6),
                  border: Border.all(
                      color: Colors.redAccent.withValues(alpha: 0.3)),
                ),
                child: Row(children: [
                  const Icon(Icons.warning_amber_rounded,
                      color: Colors.redAccent, size: 18),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      'Went to bed $tardiness minutes past target bedtime!',
                      style: const TextStyle(
                          color: Colors.redAccent,
                          fontSize: 12,
                          fontWeight: FontWeight.w500),
                    ),
                  ),
                ]),
              ),
            ],
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text('Started: ${session['start_time']}',
                    style: const TextStyle(fontSize: 11, color: Colors.grey)),
                Text('Ended: ${session['end_time']}',
                    style: const TextStyle(fontSize: 11, color: Colors.grey)),
              ],
            ),
            const SizedBox(height: 8),
            Text(
              'Noise: Avg ${session['average_noise'] ?? 0} | Max ${session['max_noise'] ?? 0} | Spikes: ${session['noise_events'] ?? 0}',
              style: const TextStyle(fontSize: 11, color: Colors.grey),
            ),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    // When actively sleeping → show full-screen sleep overlay
    if (_isSleeping) {
      return Scaffold(body: _buildActiveSleepOverlay());
    }

    return Scaffold(
      appBar: AppBar(
        title: const Text('Sleep & Metrics'),
        centerTitle: true,
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: () {
              _fetchSleepStatus();
              _fetchSleepLogs();
              _fetchScheduledTime();
            },
          ),
        ],
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : Column(
              children: [
                _buildSleepControlPanel(),
                if (_lastWakeSummary != null)
                  _buildWakeSummaryCard(_lastWakeSummary!),
                Expanded(
                  child: _sessions.isEmpty
                      ? Center(
                          child: Column(
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: [
                              Icon(Icons.bedtime_off,
                                  size: 64, color: Colors.grey.shade600),
                              const SizedBox(height: 12),
                              const Text('No sleep logs recorded yet.',
                                  style: TextStyle(color: Colors.grey)),
                            ],
                          ),
                        )
                      : ListView.builder(
                          padding: const EdgeInsets.symmetric(horizontal: 16),
                          itemCount: _sessions.length,
                          itemBuilder: (context, index) {
                            final session =
                                _sessions[_sessions.length - 1 - index];
                            return _buildSleepLogCard(session);
                          },
                        ),
                ),
              ],
            ),
    );
  }

  Widget _statBox(String value, String label) {
    return Column(
      children: [
        Text(value,
            style: const TextStyle(
                fontSize: 20,
                fontWeight: FontWeight.bold,
                color: Color(0xFFFEE000))),
        const SizedBox(height: 4),
        Text(label,
            style: const TextStyle(fontSize: 11, color: Colors.grey)),
      ],
    );
  }
}




// --------------------------------------------------
// PIKACHU ANIMATED WIDGETS
// --------------------------------------------------

class PikaSearchAnimation extends StatefulWidget {
  final double size;
  const PikaSearchAnimation({super.key, this.size = 120});

  @override
  State<PikaSearchAnimation> createState() => _PikaSearchAnimationState();
}

class _PikaSearchAnimationState extends State<PikaSearchAnimation> {
  int _frame = 0;
  Timer? _timer;
  final List<String> _frames = [
    'assets/Pikachu/peek_1.png',
    'assets/Pikachu/peek_2.png',
    'assets/Pikachu/peek_3.png',
    'assets/Pikachu/peek_4.png',
  ];

  @override
  void initState() {
    super.initState();
    _timer = Timer.periodic(const Duration(milliseconds: 400), (timer) {
      if (mounted) {
        setState(() {
          _frame = (_frame + 1) % _frames.length;
        });
      }
    });
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Image.asset(
      _frames[_frame],
      width: widget.size,
      height: widget.size,
      fit: BoxFit.contain,
      errorBuilder: (context, error, stackTrace) => const Icon(Icons.search, size: 48, color: Color(0xFFFEE000)),
    );
  }
}

class PikaSpeakingAnimation extends StatefulWidget {
  final double size;
  const PikaSpeakingAnimation({super.key, this.size = 100});

  @override
  State<PikaSpeakingAnimation> createState() => _PikaSpeakingAnimationState();
}

class _PikaSpeakingAnimationState extends State<PikaSpeakingAnimation> {
  int _frame = 0;
  Timer? _timer;
  final List<String> _frames = [
    'assets/Pikachu/eyes_open_mouth_closed.png',
    'assets/Pikachu/eyes_open_mouth_open_20.png',
    'assets/Pikachu/eyes_open_mouth_open_60.png',
    'assets/Pikachu/eyes_open_mouth_open_100.png',
  ];

  @override
  void initState() {
    super.initState();
    _timer = Timer.periodic(const Duration(milliseconds: 150), (timer) {
      if (mounted) {
        setState(() {
          _frame = (_frame + 1) % _frames.length;
        });
      }
    });
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Image.asset(
      _frames[_frame],
      width: widget.size,
      height: widget.size,
      fit: BoxFit.contain,
      errorBuilder: (context, error, stackTrace) => const Icon(Icons.record_voice_over, size: 48, color: Color(0xFFFEE000)),
    );
  }
}

class PikaSleepingAnimation extends StatefulWidget {
  final double size;
  const PikaSleepingAnimation({super.key, this.size = 110});

  @override
  State<PikaSleepingAnimation> createState() => _PikaSleepingAnimationState();
}

class _PikaSleepingAnimationState extends State<PikaSleepingAnimation> {
  int _frame = 0;
  Timer? _timer;
  final List<String> _frames = [
    'assets/Pikachu/sleep/sleep_1.png',
    'assets/Pikachu/sleep/sleep_2.png',
  ];

  @override
  void initState() {
    super.initState();
    _timer = Timer.periodic(const Duration(seconds: 1), (timer) {
      if (mounted) {
        setState(() {
          _frame = (_frame + 1) % _frames.length;
        });
      }
    });
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Image.asset(
      _frames[_frame],
      width: widget.size,
      height: widget.size,
      fit: BoxFit.contain,
      errorBuilder: (context, error, stackTrace) => const Icon(Icons.nightlight_round, size: 48, color: Color(0xFFFEE000)),
    );
  }
}

class PikaWavingAnimation extends StatefulWidget {
  final double size;
  const PikaWavingAnimation({super.key, this.size = 120});

  @override
  State<PikaWavingAnimation> createState() => _PikaWavingAnimationState();
}

class _PikaWavingAnimationState extends State<PikaWavingAnimation> {
  int _frame = 0;
  Timer? _timer;
  final List<String> _frames = [
    'assets/Pikachu/wave_1.png',
    'assets/Pikachu/wave_2.png',
    'assets/Pikachu/wave_3.png',
  ];

  @override
  void initState() {
    super.initState();
    _timer = Timer.periodic(const Duration(milliseconds: 300), (timer) {
      if (mounted) {
        setState(() {
          _frame = (_frame + 1) % _frames.length;
        });
      }
    });
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Image.asset(
      _frames[_frame],
      width: widget.size,
      height: widget.size,
      fit: BoxFit.contain,
      errorBuilder: (context, error, stackTrace) => const Icon(Icons.hourglass_empty, size: 48, color: Color(0xFFFEE000)),
    );
  }
}

// --------------------------------------------------
// SLEEP ANALYTICS SCREEN & CUSTOM BREAKDOWN VIEW
// --------------------------------------------------

class SleepAnalyticsScreen extends StatefulWidget {
  final List<dynamic> sessions;
  final String targetBedtime;

  const SleepAnalyticsScreen({
    super.key,
    required this.sessions,
    required this.targetBedtime,
  });

  @override
  State<SleepAnalyticsScreen> createState() => _SleepAnalyticsScreenState();
}

class _SleepAnalyticsScreenState extends State<SleepAnalyticsScreen> {
  // Statistics variables
  double _avgDuration = 0.0;
  double _avgTosses = 0.0;
  double _avgNoise = 0.0;
  double _avgLdr = 0.0;

  double _goodRatio = 0.0;
  double _fairRatio = 0.0;
  double _poorRatio = 0.0;

  int _totalNaps = 0;
  int _totalSleeps = 0;
  int _totalTardy = 0;
  double _avgTardyMins = 0.0;

  @override
  void initState() {
    super.initState();
    _calculateStats();
  }

  void _calculateStats() {
    if (widget.sessions.isEmpty) return;

    double totalDuration = 0.0;
    double totalTosses = 0.0;
    double totalNoise = 0.0;
    double totalLdr = 0.0;

    int goodCount = 0;
    int fairCount = 0;
    int poorCount = 0;

    int tardyCount = 0;
    double totalTardyMins = 0.0;

    for (final session in widget.sessions) {
      final duration = (session['duration_hours'] as num?)?.toDouble() ?? 0.0;
      totalDuration += duration;

      final tosses = (session['movement_count'] as num?)?.toDouble() ?? 0.0;
      totalTosses += tosses;

      final noise = (session['average_noise'] as num?)?.toDouble() ?? 0.0;
      totalNoise += noise;

      final ldr = (session['average_ldr'] as num?)?.toDouble() ?? 150.0;
      totalLdr += ldr;

      final type = (session['type'] as String?)?.toLowerCase() ?? 'sleep';
      if (type.contains('nap')) {
        _totalNaps++;
      } else {
        _totalSleeps++;
      }

      final quality = (session['quality'] as String?)?.toLowerCase() ?? 'fair';
      if (quality.contains('good')) {
        goodCount++;
      } else if (quality.contains('poor')) {
        poorCount++;
      } else {
        fairCount++;
      }

      final tardy = (session['tardiness_minutes'] as num?)?.toInt() ?? 0;
      if (tardy > 0) {
        tardyCount++;
        totalTardyMins += tardy;
      }
    }

    final len = widget.sessions.length;
    setState(() {
      _avgDuration = totalDuration / len;
      _avgTosses = totalTosses / len;
      _avgNoise = totalNoise / len;
      _avgLdr = totalLdr / len;

      _goodRatio = goodCount / len;
      _fairRatio = fairCount / len;
      _poorRatio = poorCount / len;

      _totalTardy = tardyCount;
      if (tardyCount > 0) {
        _avgTardyMins = totalTardyMins / tardyCount;
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final recentSessions = widget.sessions.length > 8 
        ? widget.sessions.sublist(widget.sessions.length - 8)
        : widget.sessions;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Sleep Diagnostics'),
        centerTitle: true,
        elevation: 0,
        backgroundColor: Colors.transparent,
      ),
      extendBodyBehindAppBar: false,
      body: widget.sessions.isEmpty
          ? Center(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  const PikaSearchAnimation(size: 140),
                  const SizedBox(height: 16),
                  const Text(
                    'No metrics to analyze yet.\nLog some sleep sessions to unlock detailed reports.',
                    style: TextStyle(color: Colors.grey),
                    textAlign: TextAlign.center,
                  ),
                ],
              ),
            )
          : SingleChildScrollView(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Header Overview
                  _buildMainMetricsHeader(),
                  const SizedBox(height: 20),

                  // Trend Chart
                  _buildTrendChart(recentSessions),
                  const SizedBox(height: 20),

                  // Diagnostics and Ratios Row
                  Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Expanded(child: _buildQualitySection()),
                      const SizedBox(width: 12),
                      Expanded(child: _buildEnvironmentalDiagnostics()),
                    ],
                  ),
                  const SizedBox(height: 20),

                  // Bedtime Tardiness Breakdown
                  _buildBedtimeAnalyticsCard(),
                  const SizedBox(height: 20),

                  // Sleep Hygiene Suggestions
                  _buildSleepHygieneCard(),
                  const SizedBox(height: 24),
                ],
              ),
            ),
    );
  }

  Widget _buildMainMetricsHeader() {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [
            const Color(0xFF7C3AED).withValues(alpha: 0.2),
            const Color(0xFF4F46E5).withValues(alpha: 0.05),
          ],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: const Color(0xFF7C3AED).withValues(alpha: 0.25)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Row(
                children: [
                  Container(
                    padding: const EdgeInsets.all(8),
                    decoration: BoxDecoration(
                      color: const Color(0xFF7C3AED).withValues(alpha: 0.2),
                      shape: BoxShape.circle,
                    ),
                    child: const Icon(Icons.auto_awesome_rounded, color: Color(0xFFC084FC), size: 20),
                  ),
                  const SizedBox(width: 10),
                  const Text(
                    'Overall Sleep Score',
                    style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: Colors.white),
                  ),
                ],
              ),
              const PikaSleepingAnimation(size: 50),
            ],
          ),
          const SizedBox(height: 16),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    _fmtDurationScore(),
                    style: const TextStyle(fontSize: 28, fontWeight: FontWeight.bold, color: Color(0xFFFEE000)),
                  ),
                  const SizedBox(height: 4),
                  const Text(
                    'Average Duration',
                    style: TextStyle(color: Colors.grey, fontSize: 12),
                  ),
                ],
              ),
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    _avgTosses.toStringAsFixed(1),
                    style: const TextStyle(fontSize: 28, fontWeight: FontWeight.bold, color: Colors.white),
                  ),
                  const SizedBox(height: 4),
                  const Text(
                    'Avg Tosses / Session',
                    style: TextStyle(color: Colors.grey, fontSize: 12),
                  ),
                ],
              ),
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    '${widget.sessions.length}',
                    style: const TextStyle(fontSize: 28, fontWeight: FontWeight.bold, color: Colors.white),
                  ),
                  const SizedBox(height: 4),
                  const Text(
                    'Sessions Logged',
                    style: TextStyle(color: Colors.grey, fontSize: 12),
                  ),
                ],
              ),
            ],
          ),
        ],
      ),
    );
  }

  String _fmtDurationScore() {
    final h = _avgDuration.toInt();
    final m = ((_avgDuration - h) * 60).toInt();
    if (h == 0) return '${m}m';
    return '${h}h ${m}m';
  }

  Widget _buildTrendChart(List<dynamic> recent) {
    return Card(
      color: const Color(0xFF1A1A1A),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                const Text(
                  'Sleep Duration Trend',
                  style: TextStyle(fontWeight: FontWeight.bold, fontSize: 14, color: Colors.white),
                ),
                Text(
                  'Last ${recent.length} Sessions',
                  style: const TextStyle(color: Colors.grey, fontSize: 11),
                ),
              ],
            ),
            const SizedBox(height: 24),
            SizedBox(
              height: 120,
              width: double.infinity,
              child: CustomPaint(
                painter: SleepDurationChartPainter(recent),
              ),
            ),
            const SizedBox(height: 10),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: const [
                Text('Older', style: TextStyle(color: Colors.grey, fontSize: 10)),
                Text('Most Recent', style: TextStyle(color: Colors.grey, fontSize: 10)),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildQualitySection() {
    return Card(
      color: const Color(0xFF1A1A1A),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          children: [
            const Text(
              'Quality Ratio',
              style: TextStyle(fontWeight: FontWeight.bold, fontSize: 13, color: Colors.white),
            ),
            const SizedBox(height: 20),
            SizedBox(
              width: 90,
              height: 90,
              child: CustomPaint(
                painter: SleepQualityPiePainter(_goodRatio, _fairRatio, _poorRatio),
                child: Center(
                  child: Text(
                    '${(_goodRatio * 100).toStringAsFixed(0)}%',
                    style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: Colors.green),
                  ),
                ),
              ),
            ),
            const SizedBox(height: 16),
            _buildQualityLegendRow(Colors.green, 'Good', _goodRatio),
            const SizedBox(height: 6),
            _buildQualityLegendRow(Colors.orange, 'Fair', _fairRatio),
            const SizedBox(height: 6),
            _buildQualityLegendRow(Colors.redAccent, 'Poor', _poorRatio),
          ],
        ),
      ),
    );
  }

  Widget _buildQualityLegendRow(Color color, String label, double ratio) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Row(
          children: [
            Container(width: 8, height: 8, decoration: BoxDecoration(color: color, shape: BoxShape.circle)),
            const SizedBox(width: 6),
            Text(label, style: const TextStyle(fontSize: 11, color: Colors.grey)),
          ],
        ),
        Text(
          '${(ratio * 100).toStringAsFixed(0)}%',
          style: const TextStyle(fontSize: 11, fontWeight: FontWeight.bold, color: Colors.white),
        ),
      ],
    );
  }

  Widget _buildEnvironmentalDiagnostics() {
    return Card(
      color: const Color(0xFF1A1A1A),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Center(
              child: Text(
                'Environment Stats',
                style: TextStyle(fontWeight: FontWeight.bold, fontSize: 13, color: Colors.white),
              ),
            ),
            const SizedBox(height: 16),
            _environmentalItem(Icons.nightlight_outlined, 'Average Light', '${_avgLdr.toStringAsFixed(0)} LDR', _ldrAssessment()),
            const Divider(height: 20, color: Colors.white10),
            _environmentalItem(Icons.volume_up_outlined, 'Noise Profile', '${_avgNoise.toStringAsFixed(0)} RMS', _noiseAssessment()),
          ],
        ),
      ),
    );
  }

  Widget _environmentalItem(IconData icon, String title, String value, String desc) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Icon(icon, size: 16, color: const Color(0xFFFEE000)),
            const SizedBox(width: 6),
            Text(title, style: const TextStyle(fontSize: 11, color: Colors.grey)),
          ],
        ),
        const SizedBox(height: 6),
        Text(value, style: const TextStyle(fontSize: 14, fontWeight: FontWeight.bold, color: Colors.white)),
        const SizedBox(height: 2),
        Text(desc, style: const TextStyle(fontSize: 10, color: Colors.grey)),
      ],
    );
  }

  String _ldrAssessment() {
    if (_avgLdr < 300) return 'Optimal pitch black darkness.';
    if (_avgLdr < 700) return 'Acceptable brightness level.';
    return 'Room too bright. Use curtains.';
  }

  String _noiseAssessment() {
    if (_avgNoise < 250) return 'Very quiet room, ideal.';
    if (_avgNoise < 500) return 'Moderate noise levels.';
    return 'Noisy ambient. Try earplugs.';
  }

  Widget _buildBedtimeAnalyticsCard() {
    final hasBedtime = widget.targetBedtime != "Not Set";
    return Card(
      color: const Color(0xFF1A1A1A),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Icon(Icons.bedtime_rounded, color: Color(0xFFFEE000), size: 18),
                const SizedBox(width: 8),
                const Text(
                  'Bedtime Schedule Adherence',
                  style: TextStyle(fontWeight: FontWeight.bold, fontSize: 13, color: Colors.white),
                ),
              ],
            ),
            const Divider(height: 24, color: Colors.white10),
            if (!hasBedtime) ...[
              const Text(
                'No bedtime scheduled. Add a target bedtime to track tardiness and schedule compliance metrics.',
                style: TextStyle(color: Colors.grey, fontSize: 12),
              ),
            ] else ...[
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  _bedtimeMetric('Target Time', widget.targetBedtime),
                  _bedtimeMetric('Tardy Rate', '${((_totalTardy / (_totalSleeps + _totalNaps)) * 100).toStringAsFixed(0)}%'),
                  _bedtimeMetric('Avg Latency', '${_avgTardyMins.toStringAsFixed(0)} mins'),
                ],
              ),
              const SizedBox(height: 12),
              Text(
                _tardyReportDescription(),
                style: const TextStyle(color: Colors.grey, fontSize: 11),
              ),
            ]
          ],
        ),
      ),
    );
  }

  Widget _bedtimeMetric(String title, String val) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(title, style: const TextStyle(color: Colors.grey, fontSize: 11)),
        const SizedBox(height: 4),
        Text(val, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: Colors.white)),
      ],
    );
  }

  String _tardyReportDescription() {
    if (_totalTardy == 0) return 'Excellent! You consistently go to sleep within your bedtime window.';
    if (_avgTardyMins < 30) return 'Good job. You are rarely late for bed, usually within 30 minutes.';
    return 'Caution: You frequently miss your scheduled bedtime. Aim to reduce late-night activities.';
  }

  Widget _buildSleepHygieneCard() {
    return Card(
      color: const Color(0xFF1E1B4B).withValues(alpha: 0.3),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(16),
        side: BorderSide(color: const Color(0xFF4F46E5).withValues(alpha: 0.3)),
      ),
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Icon(Icons.lightbulb_outline_rounded, color: Color(0xFFFEE000), size: 20),
                const SizedBox(width: 8),
                const Text(
                  'Sleep Hygiene Insights',
                  style: TextStyle(fontWeight: FontWeight.bold, fontSize: 14, color: Colors.white),
                ),
              ],
            ),
            const SizedBox(height: 12),
            Text(
              _generateHygieneRecommendation(),
              style: const TextStyle(color: Color(0xFFC7D2FE), fontSize: 12, height: 1.4),
            ),
          ],
        ),
      ),
    );
  }

  String _generateHygieneRecommendation() {
    if (_avgLdr >= 500) {
      return '• Ambient light detected is higher than normal. Turning off auxiliary lights or getting thick curtains will improve melatonin secretion.\n• Sleep environment is critical for deep stage cycles.';
    }
    if (_avgTosses >= 6.0) {
      return '• Significant motion/tosses logged. High activity usually points to light sleep. Try adjusting room temperature (aim for 18-20°C) or avoid heavy meals 3 hours before bed.';
    }
    if (_avgNoise >= 400) {
      return '• Frequent noise events/spikes recorded. Ambient sounds interfere with REM sleep. Consider white noise devices or soundproofing solutions to protect sleep continuity.';
    }
    return '• All metrics fall within ideal zones. Excellent work! Keep maintaining your scheduled bedtime and dark sleep setting to preserve high health parameters.';
  }
}

class SleepDurationChartPainter extends CustomPainter {
  final List<dynamic> sessions;
  SleepDurationChartPainter(this.sessions);

  @override
  void paint(Canvas canvas, Size size) {
    if (sessions.isEmpty) return;

    final paintLine = Paint()
      ..color = const Color(0xFFC084FC)
      ..strokeWidth = 3
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round;

    final paintPoint = Paint()
      ..color = const Color(0xFFFEE000)
      ..style = PaintingStyle.fill;

    final paintGrid = Paint()
      ..color = Colors.white10
      ..strokeWidth = 1;

    final double maxVal = sessions.map((s) => (s['duration_hours'] as num?)?.toDouble() ?? 0.0).fold(8.0, (m, v) => v > m ? v : m);
    final int count = sessions.length;
    final double stepX = count > 1 ? size.width / (count - 1) : size.width;

    // Draw horizontal grid lines
    for (int i = 0; i <= 4; i++) {
      final double y = size.height - (i * size.height / 4);
      canvas.drawLine(Offset(0, y), Offset(size.width, y), paintGrid);
    }

    final points = <Offset>[];
    for (int i = 0; i < count; i++) {
      final double duration = (sessions[i]['duration_hours'] as num?)?.toDouble() ?? 0.0;
      final double x = i * stepX;
      final double y = size.height - (duration / maxVal * size.height);
      points.add(Offset(x, y));
    }

    if (points.length > 1) {
      final path = Path()..moveTo(points.first.dx, points.first.dy);
      for (int i = 1; i < points.length; i++) {
        // Curve to make it look smooth and premium
        final p0 = points[i - 1];
        final p1 = points[i];
        final controlX1 = p0.dx + (p1.dx - p0.dx) / 2;
        path.cubicTo(controlX1, p0.dy, controlX1, p1.dy, p1.dx, p1.dy);
      }
      canvas.drawPath(path, paintLine);
    }

    for (final pt in points) {
      canvas.drawCircle(pt, 5, paintPoint);
      canvas.drawCircle(pt, 8, Paint()..color = const Color(0xFFFEE000).withValues(alpha: 0.3)..style = PaintingStyle.stroke..strokeWidth = 2);
    }
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => true;
}

class SleepQualityPiePainter extends CustomPainter {
  final double goodPct;
  final double fairPct;
  final double poorPct;

  SleepQualityPiePainter(this.goodPct, this.fairPct, this.poorPct);

  @override
  void paint(Canvas canvas, Size size) {
    final double radius = size.width / 2;
    final Offset center = Offset(size.width / 2, size.height / 2);
    final double strokeWidth = 14;

    final paintGood = Paint()
      ..color = Colors.green
      ..style = PaintingStyle.stroke
      ..strokeWidth = strokeWidth
      ..strokeCap = StrokeCap.round;

    final paintFair = Paint()
      ..color = Colors.orange
      ..style = PaintingStyle.stroke
      ..strokeWidth = strokeWidth
      ..strokeCap = StrokeCap.round;

    final paintPoor = Paint()
      ..color = Colors.redAccent
      ..style = PaintingStyle.stroke
      ..strokeWidth = strokeWidth
      ..strokeCap = StrokeCap.round;

    double startAngle = -3.14159 / 2; // top of circle

    // Draw segment by segment
    if (goodPct > 0) {
      final sweepAngle = 2 * 3.14159265 * goodPct;
      canvas.drawArc(
        Rect.fromCircle(center: center, radius: radius - strokeWidth/2),
        startAngle,
        sweepAngle,
        false,
        paintGood,
      );
      startAngle += sweepAngle;
    }

    if (fairPct > 0) {
      final sweepAngle = 2 * 3.14159265 * fairPct;
      canvas.drawArc(
        Rect.fromCircle(center: center, radius: radius - strokeWidth/2),
        startAngle,
        sweepAngle,
        false,
        paintFair,
      );
      startAngle += sweepAngle;
    }

    if (poorPct > 0) {
      final sweepAngle = 2 * 3.14159265 * poorPct;
      canvas.drawArc(
        Rect.fromCircle(center: center, radius: radius - strokeWidth/2),
        startAngle,
        sweepAngle,
        false,
        paintPoor,
      );
    }
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => true;
}

