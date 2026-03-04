const net = require('net');

// Cấu hình kết nối
const HOST = 'localhost' || '100.73.130.46';
const PORT = 8080;

// Test FEN strings
const testFENs = [
  // Starting position
  'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1',
  // After 1.e4
  'rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1',
  // After 1.e4 e5
  'rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq e6 0 2',
  // After 1.e4 e5 2.Nf3
  'rnbqkbnr/pppp1ppp/8/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R b KQkq - 1 2'
];

function createClient() {
  const client = new net.Socket();

  client.connect(PORT, HOST, function() {
    console.log('Đã kết nối tới TCP server ' + HOST + ':' + PORT);
  });

  client.on('data', function(data) {
    console.log('Nhận từ server: ' + data);
  });

  client.on('close', function() {
    console.log('Kết nối TCP đã đóng');
  });

  client.on('error', function(err) {
    console.error('Lỗi TCP:', err);
  });

  return client;
}

// Test function để gửi FEN
function sendTestFEN() {
  const client = createClient();
  let currentIndex = 0;

  client.on('connect', () => {
    console.log('Bắt đầu gửi test FEN...\n');
    
    const sendNext = () => {
      if (currentIndex < testFENs.length) {
        const fen = testFENs[currentIndex];
        const message = JSON.stringify({ fen_str: fen });
        
        console.log(`Gửi FEN ${currentIndex + 1}/${testFENs.length}:`);
        console.log(`   ${fen}`);
        
        client.write(message + '\n');
        currentIndex++;
        
        // Gửi tiếp FEN sau 3 giây
        setTimeout(sendNext, 3000);
      } else {
        console.log('\nĐã gửi xong tất cả test FEN');
        setTimeout(() => client.destroy(), 1000);
      }
    };
    
    // Bắt đầu gửi sau 1 giây
    setTimeout(sendNext, 1000);
  });
}

// Test function để gửi FEN string đơn lẻ
function sendSingleFEN(fen) {
  const client = createClient();
  
  client.on('connect', () => {
    const message = JSON.stringify({ fen_str: fen });
    console.log('Gửi FEN:', fen);
    client.write(message + '\n');
    
    setTimeout(() => client.destroy(), 2000);
  });
}

// Chạy test
console.log('TCP Client Test Tool');
console.log('=======================\n');

const args = process.argv.slice(2);

if (args.length > 0) {
  // Nếu có argument, gửi FEN string đó
  sendSingleFEN(args.join(' '));
} else {
  // Nếu không có argument, chạy test sequence
  sendTestFEN();
}

// Graceful shutdown
process.on('SIGINT', () => {
  console.log('\nStopping test client...');
  process.exit(0);
});