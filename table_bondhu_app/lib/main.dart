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
                GestureDetector(
                  onLongPressStart: (_) => _startRecording(),
                  onLongPressEnd: (_) => _stopRecordingAndSend(),
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

class _SleepScreenState extends State<SleepScreen> {
  List<dynamic> _sessions = [];
  bool _isLoading = false;
  String _scheduledTime = "Not Set";

  @override
  void initState() {
    super.initState();
    _fetchSleepLogs();
    _fetchScheduledTime();
  }

  Future<void> _fetchSleepLogs() async {
    if (!mounted) return;
    setState(() {
      _isLoading = true;
    });

    try {
      final response = await http.get(
        Uri.parse('http://${widget.serverIp}:8888/api/sleep'),
      ).timeout(const Duration(seconds: 5));

      if (response.statusCode == 200) {
        setState(() {
          _sessions = json.decode(response.body);
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

  Future<void> _fetchScheduledTime() async {
    try {
      final response = await http.get(
        Uri.parse('http://${widget.serverIp}:8888/api/sleep/schedule'),
      ).timeout(const Duration(seconds: 5));

      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        final timeStr = data['scheduled_time'];
        if (timeStr != null && timeStr.toString().isNotEmpty) {
          setState(() {
            _scheduledTime = _formatTimeStr(timeStr.toString());
          });
        }
      }
    } catch (e) {
      // Fail silently
    }
  }

  String _formatTimeStr(String militaryTime) {
    try {
      final parts = militaryTime.split(":");
      final h = int.parse(parts[0]);
      final m = int.parse(parts[1]);
      final suffix = h >= 12 ? "PM" : "AM";
      final displayH = h > 12 ? h - 12 : (h == 0 ? 12 : h);
      final displayM = m.toString().padLeft(2, '0');
      return "$displayH:$displayM $suffix";
    } catch (e) {
      return militaryTime;
    }
  }

  void _triggerInstantSleep(String type) async {
    try {
      final response = await http.post(
        Uri.parse('http://${widget.serverIp}:8888/api/sleep/start'),
        headers: {'Content-Type': 'application/json'},
        body: json.encode({'type': type}),
      ).timeout(const Duration(seconds: 5));

      if (response.statusCode == 200) {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text('Successfully started instant ${type == "sleep" ? "sleep" : "nap"}! ESP32 screen updated.')),
          );
        }
      } else {
        final errorMsg = json.decode(response.body)['error'] ?? "Unknown error";
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text(errorMsg)),
          );
        }
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Failed to connect to companion server.')),
        );
      }
    }
  }

  void _selectBedtime() async {
    final TimeOfDay? picked = await showTimePicker(
      context: context,
      initialTime: const TimeOfDay(hour: 22, minute: 0),
    );

    if (picked != null) {
      final militaryTime = "${picked.hour.toString().padLeft(2, '0')}:${picked.minute.toString().padLeft(2, '0')}";
      try {
        final response = await http.post(
          Uri.parse('http://${widget.serverIp}:8888/api/sleep/schedule'),
          headers: {'Content-Type': 'application/json'},
          body: json.encode({'time': militaryTime}),
        ).timeout(const Duration(seconds: 5));

        if (response.statusCode == 200) {
          setState(() {
            _scheduledTime = _formatTimeStr(militaryTime);
          });
          if (mounted) {
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(content: Text('Bedtime scheduled for $_scheduledTime')),
            );
          }
        }
      } catch (e) {
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

  Widget _buildSleepControlPanel() {
    return Card(
      margin: const EdgeInsets.all(16),
      color: const Color(0xFF1E1E1E),
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
                    const Text(
                      'Target Bedtime',
                      style: TextStyle(color: Colors.grey, fontSize: 13),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      _scheduledTime,
                      style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold, color: Color(0xFFFEE000)),
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
            const Divider(height: 24, color: Colors.white10),
            Row(
              children: [
                Expanded(
                  child: ElevatedButton.icon(
                    onPressed: () => _triggerInstantSleep("sleep"),
                    icon: const Icon(Icons.nightlight_round),
                    label: const Text('Instant Sleep', style: TextStyle(fontWeight: FontWeight.bold)),
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
                    label: const Text('Instant Nap', style: TextStyle(fontWeight: FontWeight.bold)),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: Colors.white12,
                      foregroundColor: Colors.white,
                      padding: const EdgeInsets.symmetric(vertical: 12),
                    ),
                  ),
                ),
              ],
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
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Row(
                  children: [
                    Icon(
                      type.toString().toLowerCase().contains("nap")
                          ? Icons.wb_sunny
                          : Icons.nightlight_round,
                      color: const Color(0xFFFEE000),
                    ),
                    const SizedBox(width: 8),
                    Text(
                      '${type.toString().toUpperCase()} SESSION',
                      style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 15),
                    ),
                  ],
                ),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                  decoration: BoxDecoration(
                    color: _getQualityColor(quality).withValues(alpha: 0.15),
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: _getQualityColor(quality), width: 1),
                  ),
                  child: Text(
                    quality.toString().toUpperCase(),
                    style: TextStyle(
                      fontSize: 11,
                      fontWeight: FontWeight.bold,
                      color: _getQualityColor(quality),
                    ),
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
                  border: Border.all(color: Colors.redAccent.withValues(alpha: 0.3)),
                ),
                child: Row(
                  children: [
                    const Icon(Icons.warning_amber_rounded, color: Colors.redAccent, size: 18),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        'Went to bed $tardiness minutes past target bedtime!',
                        style: const TextStyle(color: Colors.redAccent, fontSize: 12, fontWeight: FontWeight.w500),
                      ),
                    ),
                  ],
                ),
              ),
            ],
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(
                  'Started: ${session['start_time']}',
                  style: const TextStyle(fontSize: 11, color: Colors.grey),
                ),
                Text(
                  'Ended: ${session['end_time']}',
                  style: const TextStyle(fontSize: 11, color: Colors.grey),
                ),
              ],
            ),
            const SizedBox(height: 8),
            Text(
              'Noise profile: Avg ${session['average_noise'] ?? 0} RMS | Max ${session['max_noise'] ?? 0} RMS | Spikes: ${session['noise_events'] ?? 0}',
              style: const TextStyle(fontSize: 11, color: Colors.grey),
            ),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Sleep Metrics History'),
        centerTitle: true,
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: () {
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
                Expanded(
                  child: _sessions.isEmpty
                      ? Center(
                          child: Column(
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: [
                              Icon(Icons.bedtime_off, size: 64, color: Colors.grey.shade600),
                              const SizedBox(height: 12),
                              const Text('No sleep logs recorded yet.', style: TextStyle(color: Colors.grey)),
                            ],
                          ),
                        )
                      : ListView.builder(
                          padding: const EdgeInsets.symmetric(horizontal: 16),
                          itemCount: _sessions.length,
                          itemBuilder: (context, index) {
                            final session = _sessions[_sessions.length - 1 - index];
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
        Text(
          value,
          style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold, color: Color(0xFFFEE000)),
        ),
        const SizedBox(height: 4),
        Text(
          label,
          style: const TextStyle(fontSize: 11, color: Colors.grey),
        ),
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
