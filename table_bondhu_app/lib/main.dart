import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;

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
  String _serverIp = "192.168.0.38"; // Central Server IP state

  void _onIpConfigured(String newIp) {
    setState(() {
      _serverIp = newIp;
    });
  }

  @override
  Widget build(BuildContext context) {
    final List<Widget> screens = [
      ConnectionScreen(
        initialServerIp: _serverIp,
        onIpConfigured: _onIpConfigured,
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

  const ConnectionScreen({
    super.key,
    required this.initialServerIp,
    required this.onIpConfigured,
  });

  @override
  State<ConnectionScreen> createState() => _ConnectionScreenState();
}

class _ConnectionScreenState extends State<ConnectionScreen> {
  late TextEditingController _ssidController;
  late TextEditingController _passwordController;
  late TextEditingController _serverIpController;

  bool _isProvisioning = false;
  bool _isSearchingBeacon = false;
  String _beaconStatus = "Idle";
  String _provisioningLog = "";

  RawDatagramSocket? _udpSocket;
  StreamSubscription? _udpSubscription;

  @override
  void initState() {
    super.initState();
    _ssidController = TextEditingController(text: "Rafsan's S21");
    _passwordController = TextEditingController(text: "12345678");
    _serverIpController = TextEditingController(text: widget.initialServerIp);
  }

  @override
  void dispose() {
    _stopUdpSearch();
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

  void _startUdpSearch() async {
    setState(() {
      _isSearchingBeacon = true;
      _beaconStatus = "Listening for companion server beacon...";
    });
    _log("Starting UDP Discovery on port 9999...");

    try {
      _udpSocket = await RawDatagramSocket.bind(InternetAddress.anyIPv4, 9999);
      _udpSocket!.broadcastEnabled = true;

      _udpSubscription = _udpSocket!.listen((RawSocketEvent event) {
        if (event == RawSocketEvent.read) {
          Datagram? dg = _udpSocket!.receive();
          if (dg != null) {
            String message = utf8.decode(dg.data).trim();
            _log("Received UDP Broadcast: '$message' from ${dg.address.address}");
            
            if (message.contains("TABLE_BONDHU_BEACON")) {
              setState(() {
                _serverIpController.text = dg.address.address;
                _beaconStatus = "Server Found: ${dg.address.address}";
              });
              widget.onIpConfigured(dg.address.address);
              _log("Auto-discovered server IP: ${dg.address.address}");
              _stopUdpSearch();
            }
          }
        }
      });

      Future.delayed(const Duration(seconds: 15), () {
        if (_isSearchingBeacon) {
          _log("UDP Discovery timeout (15s exceeded).");
          _stopUdpSearch();
          setState(() {
            _beaconStatus = "Timeout. Server not detected.";
          });
        }
      });

    } catch (e) {
      _log("UDP Binding Error: $e");
      _stopUdpSearch();
    }
  }

  void _stopUdpSearch() {
    _udpSubscription?.cancel();
    _udpSocket?.close();
    if (mounted) {
      setState(() {
        _isSearchingBeacon = false;
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
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16.0),
                child: Column(
                  children: [
                    const Icon(Icons.settings_input_antenna, size: 48, color: Color(0xFFFEE000)),
                    const SizedBox(height: 12),
                    const Text(
                      'Connection Manager',
                      style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                    ),
                    const SizedBox(height: 8),
                    Text(
                      _isSearchingBeacon ? 'Scanning Local Network...' : 'Configure connection to ESP32 and Python Server',
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
            Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _serverIpController,
                    onChanged: (val) => widget.onIpConfigured(val.trim()),
                    decoration: const InputDecoration(
                      labelText: 'Python Server IP',
                      border: OutlineInputBorder(),
                      prefixIcon: Icon(Icons.computer),
                    ),
                  ),
                ),
                const SizedBox(width: 8),
                IconButton.filledTonal(
                  onPressed: _isSearchingBeacon ? _stopUdpSearch : _startUdpSearch,
                  icon: Icon(_isSearchingBeacon ? Icons.stop : Icons.search),
                  tooltip: 'Search Server IP on Network',
                ),
              ],
            ),
            if (_isSearchingBeacon || _beaconStatus != "Idle") ...[
              const SizedBox(height: 8),
              Text(
                _beaconStatus,
                style: const TextStyle(color: Color(0xFFFEE000), fontSize: 13, fontWeight: FontWeight.w500),
                textAlign: TextAlign.center,
              ),
            ],
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

  @override
  void initState() {
    super.initState();
    _messages.add(ChatMessage(
      text: "Hello! I am Table-Bondhu. How can I help you today?",
      isUser: false,
      timestamp: DateTime.now(),
    ));
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
              child: Center(child: CircularProgressIndicator()),
            ),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 8.0, vertical: 4.0),
            color: Colors.black26,
            child: Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _messageController,
                    onSubmitted: (_) => _sendMessage(),
                    decoration: const InputDecoration(
                      hintText: 'Type your prompt here...',
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
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
        constraints: BoxConstraints(maxWidth: MediaQuery.of(context).size.width * 0.75),
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
                      Icon(Icons.alarm_off, size: 64, color: Colors.grey.shade600),
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
                  width: 220,
                  height: 220,
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
                    Text(
                      _isRunning ? _formatDuration(_secondsLeft) : "00:00",
                      style: const TextStyle(fontSize: 48, fontWeight: FontWeight.bold),
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
// 5. SLEEP HISTORY
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

  @override
  void initState() {
    super.initState();
    _fetchSleepLogs();
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

  Color _getQualityColor(String quality) {
    final q = quality.toLowerCase();
    if (q.contains("good")) return Colors.green;
    if (q.contains("poor")) return Colors.redAccent;
    return Colors.orange;
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
            onPressed: _fetchSleepLogs,
          ),
        ],
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : _sessions.isEmpty
              ? Center(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(Icons.bedtime_off, size: 64, color: Colors.grey.shade600),
                      const SizedBox(height: 12),
                      const Text('No sleep session logs recorded yet.', style: TextStyle(color: Colors.grey)),
                    ],
                  ),
                )
              : ListView.builder(
                  padding: const EdgeInsets.all(16),
                  itemCount: _sessions.length,
                  itemBuilder: (context, index) {
                    final session = _sessions[_sessions.length - 1 - index];
                    final quality = session['quality'] ?? "Fair";
                    final duration = session['duration_hours'] ?? 0.0;
                    final type = session['type'] ?? "sleep";

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
                                    color: _getQualityColor(quality).withAlpha(38),
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
                  },
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
