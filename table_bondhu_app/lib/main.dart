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

  final List<Widget> _screens = [
    const ConnectionScreen(),
    const ChatScreenPlaceholder(),
    const RemindersScreenPlaceholder(),
    const TimerScreenPlaceholder(),
    const SleepScreenPlaceholder(),
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(child: _screens[_selectedIndex]),
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
            label: 'Alarms',
          ),
          NavigationDestination(
            icon: Icon(Icons.hourglass_empty),
            label: 'Timer',
          ),
          NavigationDestination(
            icon: Icon(Icons.bedtime),
            label: 'Sleep',
          ),
        ],
      ),
    );
  }
}

// ==========================================
// 1. CONNECTION SCREEN (ACTIVE IMPLEMENTATION)
// ==========================================
class ConnectionScreen extends StatefulWidget {
  const ConnectionScreen({super.key});

  @override
  State<ConnectionScreen> createState() => _ConnectionScreenState();
}

class _ConnectionScreenState extends State<ConnectionScreen> {
  final _ssidController = TextEditingController(text: "Rafsan's S21");
  final _passwordController = TextEditingController(text: "12345678");
  final _serverIpController = TextEditingController(text: "10.25.55.20");

  bool _isProvisioning = false;
  bool _isSearchingBeacon = false;
  String _beaconStatus = "Idle";
  String _provisioningLog = "";

  RawDatagramSocket? _udpSocket;
  StreamSubscription? _udpSubscription;

  @override
  void dispose() {
    _stopUdpSearch();
    _ssidController.dispose();
    _passwordController.dispose();
    _serverIpController.dispose();
    super.dispose();
  }

  void _log(String message) {
    setState(() {
      _provisioningLog += "[${DateTime.now().toString().substring(11, 19)}] $message\n";
    });
  }

  // --- UDP Server Discovery ---
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
            
            // Check if beacon is matching
            if (message.contains("TABLE_BONDHU_BEACON")) {
              setState(() {
                _serverIpController.text = dg.address.address;
                _beaconStatus = "Server Found: ${dg.address.address}";
              });
              _log("Auto-discovered server IP: ${dg.address.address}");
              _stopUdpSearch();
            }
          }
        }
      });

      // Timeout after 15 seconds
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
    setState(() {
      _isSearchingBeacon = false;
    });
  }

  // --- Send Config to ESP32 Web Server ---
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
      // POST config values to the ESP32 in Config Mode
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
        _log("ESP32 Response: ${response.body}");
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Provisioning successful! ESP32 restarting...')),
          );
        }
      } else {
        _log("Error: Server responded with status code ${response.statusCode}");
      }
    } catch (e) {
      _log("Connection failed: Is your phone connected to the 'Table-Bondhu-Config' WiFi AP?");
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Failed to connect to ESP32 Access Point.')),
        );
      }
    } finally {
      setState(() {
        _isProvisioning = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Table-Bondhu Config'),
        centerTitle: true,
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // Status Card
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
                      _isSearchingBeacon ? 'Scanning Local Network...' : 'Enter credentials or auto-discover server.',
                      textAlign: TextAlign.center,
                      style: const TextStyle(color: Colors.grey),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 16),

            // Form Fields
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

            // Action Button
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

            // Logs output
            const Text(
              'Activity Log',
              style: TextStyle(fontWeight: FontWeight.bold, color: Colors.grey),
            ),
            const SizedBox(height: 8),
            Container(
              height: 150,
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
                  style: const TextStyle(fontFamily: 'monospace', fontSize: 12, color: Colors.green),
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
// 2. CHAT SCREEN (PLACEHOLDER)
// ==========================================
class ChatScreenPlaceholder extends StatelessWidget {
  const ChatScreenPlaceholder({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('LLM Voice Chat')),
      body: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.mic, size: 80, color: Theme.of(context).colorScheme.primary.withOpacity(0.5)),
            const SizedBox(height: 16),
            const Text(
              'Voice Chat History & Control',
              style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 8),
            const Padding(
              padding: EdgeInsets.symmetric(horizontal: 32),
              child: Text(
                'View conversation history with Pikachu, trigger speech generation, or type text commands directly to the desk companion.',
                textAlign: TextAlign.center,
                style: TextStyle(color: Colors.grey),
              ),
            ),
            const SizedBox(height: 24),
            ElevatedButton.icon(
              onPressed: () {},
              icon: const Icon(Icons.speaker_phone),
              label: const Text('Simulate Voice Activation'),
            ),
          ],
        ),
      ),
    );
  }
}

// ==========================================
// 3. REMINDERS & ALARMS (PLACEHOLDER)
// ==========================================
class RemindersScreenPlaceholder extends StatelessWidget {
  const RemindersScreenPlaceholder({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Alarms & Reminders')),
      body: ListView(
        padding: const EdgeInsets.all(16.0),
        children: [
          _buildPlaceholderCard(
            context,
            'Active Alarm',
            'Wake up for classes',
            '07:30 AM (Daily)',
            Icons.alarm,
            true,
          ),
          _buildPlaceholderCard(
            context,
            'Reminder',
            'Submit IoT Assignment',
            '02:00 PM (Today)',
            Icons.task_alt,
            true,
          ),
          _buildPlaceholderCard(
            context,
            'Reminder',
            'Team Meeting',
            '08:00 PM (Tomorrow)',
            Icons.people,
            false,
          ),
          const SizedBox(height: 16),
          FloatingActionButton.extended(
            onPressed: () {},
            label: const Text('Add Alarm / Reminder'),
            icon: const Icon(Icons.add),
          ),
        ],
      ),
    );
  }

  Widget _buildPlaceholderCard(BuildContext context, String category, String title, String time, IconData icon, bool active) {
    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: ListTile(
        leading: CircleAvatar(
          backgroundColor: Theme.of(context).colorScheme.primary.withOpacity(0.1),
          child: Icon(icon, color: Theme.of(context).colorScheme.primary),
        ),
        title: Text(title, style: const TextStyle(fontWeight: FontWeight.bold)),
        subtitle: Text('$category • $time', style: const TextStyle(color: Colors.grey)),
        trailing: Switch(
          value: active,
          onChanged: (val) {},
        ),
      ),
    );
  }
}

// ==========================================
// 4. COUNTDOWN TIMER (PLACEHOLDER)
// ==========================================
class TimerScreenPlaceholder extends StatelessWidget {
  const TimerScreenPlaceholder({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Focus Timer')),
      body: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Stack(
              alignment: Alignment.center,
              children: [
                SizedBox(
                  width: 200,
                  height: 200,
                  child: CircularProgressIndicator(
                    value: 0.65,
                    strokeWidth: 12,
                    backgroundColor: Colors.white10,
                    color: Theme.of(context).colorScheme.primary,
                  ),
                ),
                Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const Text(
                      '16:15',
                      style: TextStyle(fontSize: 48, fontWeight: FontWeight.bold),
                    ),
                    Text(
                      'of 25 mins',
                      style: TextStyle(color: Colors.grey.shade400),
                    ),
                  ],
                ),
              ],
            ),
            const SizedBox(height: 48),
            const Text(
              'Focus Session: Study Mode',
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.w500),
            ),
            const SizedBox(height: 24),
            Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                IconButton.filledTonal(
                  onPressed: () {},
                  icon: const Icon(Icons.pause),
                  iconSize: 32,
                ),
                const SizedBox(width: 24),
                IconButton.filled(
                  onPressed: () {},
                  icon: const Icon(Icons.stop),
                  iconSize: 32,
                  style: IconButton.styleFrom(
                    backgroundColor: Colors.redAccent,
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

// ==========================================
// 5. SLEEP HISTORY (PLACEHOLDER)
// ==========================================
class SleepScreenPlaceholder extends StatelessWidget {
  const SleepScreenPlaceholder({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Sleep Monitor')),
      body: ListView(
        padding: const EdgeInsets.all(16.0),
        children: [
          Card(
            color: const Color(0xFF2C2C2C),
            child: Padding(
              padding: const EdgeInsets.all(16.0),
              child: Column(
                children: [
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      const Text(
                        'Last Night\'s Sleep',
                        style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                      ),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                        decoration: BoxDecoration(
                          color: Colors.green.shade800,
                          borderRadius: BorderRadius.circular(12),
                        ),
                        child: const Text('GOOD', style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold)),
                      ),
                    ],
                  ),
                  const SizedBox(height: 16),
                  const Row(
                    mainAxisAlignment: MainAxisAlignment.spaceAround,
                    children: [
                      _SleepStat(value: '7.8h', label: 'Duration'),
                      _SleepStat(value: '4', label: 'Tosses'),
                      _SleepStat(value: '120', label: 'Avg LDR'),
                    ],
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 16),
          const Text('Recent Sessions', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
          const SizedBox(height: 8),
          _buildSleepSessionTile('July 9', 'Sleep', '8.2 hours', 'Good', Colors.green),
          _buildSleepSessionTile('July 8', 'Nap', '1.5 hours', 'Fair', Colors.orange),
          _buildSleepSessionTile('July 7', 'Sleep', '6.5 hours', 'Poor (Noisy)', Colors.redAccent),
        ],
      ),
    );
  }

  Widget _buildSleepSessionTile(String date, String type, String duration, String quality, Color qualityColor) {
    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      child: ListTile(
        leading: CircleAvatar(
          backgroundColor: Colors.white10,
          child: Icon(type == 'Sleep' ? Icons.nightlight_round : Icons.wb_sunny, color: const Color(0xFFFEE000)),
        ),
        title: Text('$type Session • $date'),
        subtitle: Text('Duration: $duration'),
        trailing: Text(
          quality,
          style: TextStyle(fontWeight: FontWeight.bold, color: qualityColor),
        ),
      ),
    );
  }
}

class _SleepStat extends StatelessWidget {
  final String value;
  final String label;

  const _SleepStat({required this.value, required this.label});

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Text(
          value,
          style: const TextStyle(fontSize: 22, fontWeight: FontWeight.bold, color: Color(0xFFFEE000)),
        ),
        const SizedBox(height: 4),
        Text(
          label,
          style: const TextStyle(fontSize: 12, color: Colors.grey),
        ),
      ],
    );
  }
}
