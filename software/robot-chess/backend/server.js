const net = require('net');
const WebSocket = require('ws');
require('dotenv').config();

// Config from environment variables
const PRIMARY_IP = process.env.PRIMARY_IP || '127.0.0.1';
const FALLBACK_IP = process.env.FALLBACK_IP || '127.0.0.1';
const TCP_PORT = process.env.TCP_PORT || 8080;
const WS_PORT = process.env.WS_PORT || 8081;
const CONNECTION_TIMEOUT = process.env.CONNECTION_TIMEOUT || 3000;

// Alternative ports
const ALT_TCP_PORTS = process.env.ALT_TCP_PORTS ? process.env.ALT_TCP_PORTS.split(',').map(p => parseInt(p)) : [8083, 8084];
const ALT_WS_PORTS = process.env.ALT_WS_PORTS ? process.env.ALT_WS_PORTS.split(',').map(p => parseInt(p)) : [8085, 8086, 8087];

// Store clients
let webSocketClients = new Set();
let tcpClients = new Set();
let robotClients = new Set(); // Separate for robot clients
let aiClients = new Set(); // Separate for AI clients
let currentServerIP = null;

// Broadcast FEN to all WebSocket clients
function broadcastToWebSocketClients(data) {
  const message = JSON.stringify(data);
  webSocketClients.forEach(client => {
    if (client.readyState === WebSocket.OPEN) {
      client.send(message);
    }
  });
}

// Send command to robot clients qua TCP
function sendCommandToRobotClients(command) {
  console.log(`Đang gửi lệnh đến ${robotClients.size} robot clients`);
  
  robotClients.forEach(robotSocket => {
    try {
      const commandStr = JSON.stringify(command);
      robotSocket.write(commandStr + '\n');
      console.log('Đã gửi đến robot:', commandStr);
    } catch (error) {
      console.error('Lỗi gửi đến robot:', error);
      robotClients.delete(robotSocket);
    }
  });
}

// Send request to AI clients qua TCP
function sendRequestToAIClients(request) {
  console.log(`Đang gửi yêu cầu đến ${aiClients.size} AI clients`);
  
  aiClients.forEach(aiSocket => {
    try {
      const requestStr = JSON.stringify(request);
      aiSocket.write(requestStr + '\n');
      console.log('Đã gửi đến AI:', requestStr);
    } catch (error) {
      console.error('Lỗi gửi đến AI:', error);
      aiClients.delete(aiSocket);
    }
  });
}

// Create TCP server for robot/external clients
const tcpServer = net.createServer((socket) => {
  console.log('TCP client đã kết nối từ:', socket.remoteAddress + ':' + socket.remotePort);
  tcpClients.add(socket);

  // Set encoding
  socket.setEncoding('utf8');

  // Process received data
  socket.on('data', (data) => {
    try {
      const message = data.toString().trim();
      console.log('Nhận được dữ liệu từ TCP client:', message);

      // Check if this is robot client identify
      try {
        const parsed = JSON.parse(message);
        
        if (parsed.type === 'robot_identify') {
          console.log('Robot client đã được xác định:', parsed.robot_id);
          robotClients.add(socket);
          socket.isRobot = true;
          socket.robotId = parsed.robot_id;
          
          socket.write(JSON.stringify({
            status: 'robot_registered',
            message: 'Robot đã được đăng ký thành công',
            robot_id: parsed.robot_id,
            timestamp: new Date().toISOString()
          }) + '\n');
          return;
        }
        
        // Check if this is AI client identify
        if (parsed.type === 'ai_identify') {
          console.log('AI client đã được xác định:', parsed.ai_id);
          aiClients.add(socket);
          socket.isAI = true;
          socket.aiId = parsed.ai_id;
          
          socket.write(JSON.stringify({
            status: 'ai_registered',
            message: 'AI đã được đăng ký thành công',
            ai_id: parsed.ai_id,
            timestamp: new Date().toISOString()
          }) + '\n');
          return;
        }
        
        // If this is robot response
        if (parsed.goal_id && parsed.success !== undefined) {
          console.log('Nhận được phản hồi từ robot:', parsed);
          
          // Broadcast response to WebSocket clients
          broadcastToWebSocketClients({
            type: 'robot_response',
            success: parsed.success,
            goal_id: parsed.goal_id,
            response: parsed,
            timestamp: new Date().toISOString()
          });
          return;
        }
        
        // Process AI response with FEN and robot command
        if (parsed.fen_str && parsed.move) {
          console.log('Nhận được AI response với FEN và robot command:', parsed);
          
          // 1. Broadcast FEN to WebSocket clients (frontend)
          broadcastToWebSocketClients({
            fen_str: parsed.fen_str,
            timestamp: new Date().toISOString(),
            source: 'ai'
          });
          
          // 2. Create robot command from AI move and send to robot clients
          const robotCommand = {
            goal_id: `ai_cmd_${Date.now().toString().slice(-6)}`,
            header: {
              timestamp: new Date().toISOString(),
              // source: 'ai',
              // ai_id: socket.aiId || 'unknown'
            },
            move: parsed.move
          };
          
          console.log('Send robot command từ AI:', robotCommand.goal_id);
          sendCommandToRobotClients(robotCommand);
          
          // 3. Broadcast AI move info to WebSocket clients
          broadcastToWebSocketClients({
            type: 'ai_move_executed',
            goal_id: robotCommand.goal_id,
            move: parsed.move,
            // ai_id: socket.aiId || 'unknown',
            timestamp: new Date().toISOString()
          });
          
          // 4. Send acknowledgment back to AI client
          socket.write(JSON.stringify({
            status: 'ai_command_processed',
            goal_id: robotCommand.goal_id,
            message: 'FEN đã được phát rộng và robot command đã được gửi',
            timestamp: new Date().toISOString()
          }) + '\n');
          return;
        }
        
        // Process AI response with best move (legacy format - for compatibility)
        if (parsed.best_move && parsed.evaluation !== undefined) {
          console.log('Nhận được phản hồi từ AI (format cũ):', parsed);
          broadcastToWebSocketClients({
            type: 'ai_response',
            best_move: parsed.best_move,
            evaluation: parsed.evaluation,
            ai_id: socket.aiId,
            response: parsed,
            timestamp: new Date().toISOString()
          });
          return;
        }
      } catch (e) {
        // Not JSON, continue processing as FEN
      }

      // Parse message - can be JSON or plain FEN string
      let fenData;
      
      try {
        // Try parsing JSON first
        const parsed = JSON.parse(message);
        if (parsed.fen_str || parsed.fen) {
          fenData = {
            fen_str: parsed.fen_str || parsed.fen,
            timestamp: new Date().toISOString(),
            source: 'tcp'
          };
        }
      } catch (e) {
        // If not JSON, treat as plain FEN string
        if (message.match(/^[rnbqkpRNBQKP1-8\/\s\-]+$/)) {
          fenData = {
            fen_str: message,
            timestamp: new Date().toISOString(),
            source: 'tcp'
          };
        }
      }

      if (fenData) {
        console.log('FEN hợp lệ đã nhận được:', fenData.fen_str);
        
        // Send to all WebSocket clients (frontend)
        broadcastToWebSocketClients(fenData);
        
        // Send response back to TCP client
        socket.write(JSON.stringify({
          status: 'success',
          message: 'FEN đã được nhận và phát rộng',
          timestamp: new Date().toISOString()
        }) + '\n');
      } else {
        console.log('Định dạng thông điệp không được nhận dạng');
        socket.write(JSON.stringify({
          status: 'error',
          message: 'Định dạng thông điệp không xác định',
          timestamp: new Date().toISOString()
        }) + '\n');
      }

    } catch (error) {
      console.error('Lỗi xử lý dữ liệu:', error);
      socket.write(JSON.stringify({
        status: 'error',
        message: 'Lỗi xử lý server',
        timestamp: new Date().toISOString()
      }) + '\n');
    }
  });

  // Handle client disconnect
  socket.on('end', () => {
    console.log('TCP client đã ngắt kết nối');
    tcpClients.delete(socket);
    if (socket.isRobot) {
      robotClients.delete(socket);
      console.log(`Robot ${socket.robotId} đã ngắt kết nối`);
    }
    if (socket.isAI) {
      aiClients.delete(socket);
      console.log(`AI ${socket.aiId} đã ngắt kết nối`);
    }
  });

  // Handle error
  socket.on('error', (err) => {
    console.error('Lỗi TCP Socket:', err);
    tcpClients.delete(socket);
    if (socket.isRobot) {
      robotClients.delete(socket);
    }
    if (socket.isAI) {
      aiClients.delete(socket);
    }
  });

  // // Send welcome message
  // socket.write(JSON.stringify({
  //   status: 'connected',
  //   message: 'Welcome to Robot Chess TCP Server',
  //   timestamp: new Date().toISOString(),
  //   instructions: {
  //     robot_identify: 'Send {"type": "robot_identify", "robot_id": "your_robot_id"}',
  //     ai_identify: 'Send {"type": "ai_identify", "ai_id": "your_ai_id"}',
  //     fen_data: 'Send FEN as JSON: {"fen_str": "your_fen"} or plain FEN string',
  //     robot_response: 'Send robot response with goal_id and success status',
  //     ai_command: 'AI sends FEN + robot command: {"fen_str": "fen", "move": {"type": "attack/move", "from": "d1", "to": "f7", "from_piece": "black_queen", "to_piece": "white_knight", "notation": "Qd1xf7+", "results_in_check": true}}',
  //     ai_response_legacy: 'Send AI response (legacy format) with best_move and evaluation'
  //   }
  // }) + '\n');
});

// Handle server error
tcpServer.on('error', (err) => {
  console.error('Lỗi TCP Server:', err);
});

// Function to try binding server to specific IP
function tryBindServer(ip, port, serverType = 'TCP') {
  return new Promise((resolve, reject) => {
    const testServer = net.createServer();
    
    testServer.on('error', (err) => {
      testServer.close();
      reject(err);
    });

    testServer.listen(port, ip, () => {
      console.log(`${serverType} server có thể bind được vào ${ip}:${port}`);
      testServer.close();
      resolve(ip);
    });
  });
}

// Function to find available port
async function findAvailablePort(ip, primaryPort, altPorts, serverType) {
  // Try main port first
  try {
    await tryBindServer(ip, primaryPort, serverType);
    return primaryPort;
  } catch (error) {
    console.log(`Port ${primaryPort} đã bị chiếm, thử ports thay thế...`);
  }

  // Try alternative ports
  for (const port of altPorts) {
    try {
      await tryBindServer(ip, port, serverType);
      console.log(`Sử dụng port thay thế: ${port}`);
      return port;
    } catch (error) {
      console.log(`Port ${port} cũng bị chiếm...`);
    }
  }

  throw new Error(`Không tìm thấy port khả dụng cho ${serverType} trên ${ip}`);
}

// Function to start TCP server with fallback IP
async function startTCPServer() {
  let serverIP = FALLBACK_IP; // Default fallback
  let serverPort = TCP_PORT;
  
  try {
    // Try binding to main IP first
    console.log(`Thử kết nối TCP server vào IP chính: ${PRIMARY_IP}:${TCP_PORT}`);
    serverPort = await findAvailablePort(PRIMARY_IP, TCP_PORT, ALT_TCP_PORTS, 'TCP');
    serverIP = PRIMARY_IP;
    console.log(`Sử dụng IP chính: ${PRIMARY_IP}:${serverPort}`);
  } catch (error) {
    console.log(`Không thể bind vào IP chính ${PRIMARY_IP}: ${error.message}`);
    console.log(`Fallback sang IP phụ: ${FALLBACK_IP}`);
    
    try {
      serverPort = await findAvailablePort(FALLBACK_IP, TCP_PORT, ALT_TCP_PORTS, 'TCP');
      serverIP = FALLBACK_IP;
      console.log(`Sử dụng IP fallback: ${FALLBACK_IP}:${serverPort}`);
    } catch (fallbackError) {
      console.error(`Không thể bind vào cả hai IP: ${fallbackError.message}`);
      process.exit(1);
    }
  }

  currentServerIP = `${serverIP}:${serverPort}`;

  // Start TCP server with selected IP and port
  tcpServer.listen(serverPort, serverIP, () => {
    console.log(`TCP server đang chạy trên ${serverIP}:${serverPort}`);
    console.log(`Để test, kết nối bằng telnet: telnet ${serverIP} ${serverPort}`);
    console.log(`Send FEN string: {"fen_str": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"}`);
  });

  return { ip: serverIP, port: serverPort };
}

// Function to start WebSocket server with fallback IP
async function startWebSocketServer() {
  let wsIP = FALLBACK_IP; // Default fallback
  let wsPort = WS_PORT;
  
  try {
    // Try binding to main IP first
    console.log(`Thử kết nối WebSocket server vào IP chính: ${PRIMARY_IP}:${WS_PORT}`);
    wsPort = await findAvailablePort(PRIMARY_IP, WS_PORT, ALT_WS_PORTS, 'WebSocket');
    wsIP = PRIMARY_IP;
    console.log(`WebSocket sử dụng IP chính: ${PRIMARY_IP}:${wsPort}`);
  } catch (error) {
    console.log(`WebSocket không thể bind vào IP chính ${PRIMARY_IP}: ${error.message}`);
    console.log(`WebSocket fallback sang IP phụ: ${FALLBACK_IP}`);
    
    try {
      wsPort = await findAvailablePort(FALLBACK_IP, WS_PORT, ALT_WS_PORTS, 'WebSocket');
      wsIP = FALLBACK_IP;
      console.log(`WebSocket sử dụng IP fallback: ${FALLBACK_IP}:${wsPort}`);
    } catch (fallbackError) {
      console.error(`WebSocket không thể bind vào cả hai IP: ${fallbackError.message}`);
      // WebSocket is optional, can continue without WebSocket
      console.log(`Tiếp tục mà không có WebSocket server...`);
      return null;
    }
  }

  // Create WebSocket server with selected IP and port
  const wss = new WebSocket.Server({ 
    port: wsPort,
    host: wsIP
  });
  
  console.log(`WebSocket server đang chạy trên ${wsIP}:${wsPort}`);

  wss.on('connection', (ws) => {
    console.log('WebSocket client đã kết nối');
    webSocketClients.add(ws);

    ws.on('message', async (message) => {
      try {
        const data = JSON.parse(message.toString());
        console.log('WebSocket message nhận được:', data);

        // Check if this is robot command
        if (data.goal_id && data.move) {
          console.log('Đang xử lý lệnh robot:', data.goal_id);
          
          // Send command đến robot clients qua TCP
          sendCommandToRobotClients(data);
          
          // Send acknowledgment về client
          ws.send(JSON.stringify({
            type: 'command_sent',
            goal_id: data.goal_id,
            message: 'Lệnh đã được gửi đến robot',
            timestamp: new Date().toISOString()
          }));
          
          console.log('Lệnh robot đã được gửi đến các robot kết nối');
          
        } else if (data.type === 'ai_request' && data.fen_position) {
          console.log('Đang xử lý yêu cầu AI:', data.request_id);
          
          // Send request đến AI clients qua TCP
          sendRequestToAIClients(data);
          
          // Send acknowledgment về client
          ws.send(JSON.stringify({
            type: 'ai_request_sent',
            request_id: data.request_id,
            message: 'Yêu cầu đã được gửi đến AI',
            timestamp: new Date().toISOString()
          }));
          
          console.log('Yêu cầu AI đã được gửi đến các AI kết nối');
          
        } else {
          // Other message (could be FEN or status)
          console.log('Phát rộng message đến các client khác');
          broadcastToWebSocketClients(data);
        }
        
      } catch (error) {
        console.error('Lỗi parse WebSocket message:', error);
        ws.send(JSON.stringify({
          type: 'error',
          message: 'Định dạng message không hợp lệ',
          error: error.message
        }));
      }
    });

    ws.on('close', () => {
      console.log('WebSocket client đã ngắt kết nối');
      webSocketClients.delete(ws);
    });

    ws.on('error', (err) => {
      console.error('Lỗi WebSocket:', err);
      webSocketClients.delete(ws);
    });

    // // Send welcome message
    // ws.send(JSON.stringify({
    //   type: 'connection',
    //   message: 'Connected to Robot Chess Server',
    //   capabilities: ['fen_broadcast', 'robot_commands', 'ai_requests', 'ai_command_execution'],
    //   connected_robots: robotClients.size,
    //   connected_ais: aiClients.size,
    //   timestamp: new Date().toISOString()
    // }));
  });

  return { wss, ip: wsIP, port: wsPort };
}

// Start servers
async function startServers() {
  console.log('=== Robot Chess Integrated Server ===');
  console.log(`IP chính: ${PRIMARY_IP}`);
  console.log(`IP fallback: ${FALLBACK_IP}`);
  console.log(`TCP Port (ALL): ${TCP_PORT} (thay thế: ${ALT_TCP_PORTS.join(', ')})`);
  console.log(`WebSocket Port: ${WS_PORT} (thay thế: ${ALT_WS_PORTS.join(', ')})`);
  console.log('=====================================\n');

  try {
    // Start WebSocket server first
    const wsResult = await startWebSocketServer();
    
    // Start TCP server
    const tcpResult = await startTCPServer();

    console.log('\nServer đã khởi động thành công!');
    console.log(`TCP (ALL): ${tcpResult.ip}:${tcpResult.port}`);
    if (wsResult) {
      console.log(`WebSocket (Frontend): ${wsResult.ip}:${wsResult.port}`);
    }    
    // Update graceful shutdown
    process.on('SIGINT', () => {
      console.log('\nĐang shutdown server...');
      tcpServer.close(() => {
        console.log('TCP server đã shutdown');
      });
      if (wsResult && wsResult.wss) {
        wsResult.wss.close(() => {
          console.log('WebSocket server đã shutdown');
        });
      }
      process.exit(0);
    });

  } catch (error) {
    console.error('Lỗi khởi động servers:', error);
    process.exit(1);
  }
}

// Start all servers
startServers();

// Log status every 30 seconds
setInterval(() => {
  const serverInfo = currentServerIP ? `(${currentServerIP})` : '';
  console.log(`Trạng thái: ${tcpClients.size} TCP clients (${robotClients.size} robots, ${aiClients.size} AIs), ${webSocketClients.size} WebSocket clients ${serverInfo}`);
}, 30000);