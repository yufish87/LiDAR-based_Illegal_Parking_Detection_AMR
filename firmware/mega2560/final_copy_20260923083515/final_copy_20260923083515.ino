#include <AccelStepper.h>

// --- 腳位與機器人參數定義 ---
float wheelBase = 0.85;      // 兩輪軸距 (m)
float wheelDiameter = 0.26; // 輪徑 (m)
int stepsPerRev = 1600;     // 驅動器細分設定 (步/圈)

const int L_stepPin = 6;  const int L_dirPin = 7;
const int L_encA = 2;     const int L_encB = 3; 
const int R_stepPin = 8;  const int R_dirPin = 9;
const int R_encA = 20;    const int R_encB = 21; 

volatile long L_pulseCount = 0;
volatile long R_pulseCount = 0;

// 運動控制變數
float targetLinear = 0;  // 線速度 (m/s)
float targetAngular = 0; // 角速度 (rad/s)
unsigned long lastCmdTime = 0;

// --- 宣告 AccelStepper 物件 ---
// 使用 DRIVER 模式 (參數 1)，專門控制 PUL/DIR 驅動器
AccelStepper stepperL(AccelStepper::DRIVER, L_stepPin, L_dirPin);
AccelStepper stepperR(AccelStepper::DRIVER, R_stepPin, R_dirPin);

void setup() {
  Serial.begin(115200);
  
  // 初始化編碼器腳位
  pinMode(L_encA, INPUT_PULLUP); pinMode(L_encB, INPUT_PULLUP);
  pinMode(R_encA, INPUT_PULLUP); pinMode(R_encB, INPUT_PULLUP);
  
  attachInterrupt(digitalPinToInterrupt(L_encA), updateEncoderL, CHANGE);
  attachInterrupt(digitalPinToInterrupt(L_encB), updateEncoderL, CHANGE);
  attachInterrupt(digitalPinToInterrupt(R_encA), updateEncoderR, CHANGE);
  attachInterrupt(digitalPinToInterrupt(R_encB), updateEncoderR, CHANGE);

  // --- AccelStepper 初始化設定 ---
  // 設定一個高於你實際運作的最大速度上限 (步/秒)
  stepperL.setMaxSpeed(20000.0);
  stepperR.setMaxSpeed(20000.0);
  stepperL.setAcceleration(50.0); 
  stepperR.setAcceleration(50.0);
}

void loop() {
  // 1. 接收來自 Python / twist_keyboard 的指令
  if (Serial.available() > 0) {
    char head = Serial.read();
    if (head == 'V') {
      targetLinear = Serial.parseFloat();
      targetAngular = Serial.parseFloat();
      lastCmdTime = millis(); 
    }
  }

  // 2. 安全機制：超過 0.5 秒沒指令就煞車
  if (millis() - lastCmdTime > 500) {
    targetLinear = 0;
    targetAngular = 0;
  }

  // 3. 計算並更新馬達速度 (此時不打脈衝，只更新速度參數)
  executeMotorControl(targetLinear, targetAngular);

  // 4. 🚨 核心：驅動馬達運轉
  // runSpeed() 會根據 setSpeed() 設定的速度，判斷現在該不該打一個脈衝
  // 它必須在 loop 裡面以極快速度被狂刷
  stepperL.run();
  stepperR.run();

  // 5. 定期回報位置 (每 50ms)
  static unsigned long lastOdomTime = 0;
  if (millis() - lastOdomTime > 50) {
    sendOdomToPC();
    lastOdomTime = millis();
  }
}

void executeMotorControl(float v, float w) {
  // 1. 算出左右輪的物理速度 (m/s)
  float leftSpeedMps = v - (w * wheelBase / 2.0);
  float rightSpeedMps = v + (w * wheelBase / 2.0);

  // 2. 物理速度 (m/s) 轉換成 步進馬達的「步數速度 (steps/s)」
  float wheelCircumference = 3.14159265 * wheelDiameter;
  float leftStepsPerSec = (leftSpeedMps / wheelCircumference) * stepsPerRev;
  float rightStepsPerSec = (rightSpeedMps / wheelCircumference) * stepsPerRev;

  // 3. 🚨 核心修改：動態調整最大速度，並給予一個該方向極遠的目標位置
  
  // 處理左輪
  if (leftStepsPerSec == 0) {
    stepperL.moveTo(stepperL.currentPosition()); // 如果速度是 0，目標就是現在位置（減速煞車）
  } else {
    stepperL.setMaxSpeed(abs(leftStepsPerSec)); // 動態限制這次的最大速度
    // 如果速度是正的，就讓目標變成目前位置 + 100000 步；負的就 - 100000 步
    long targetL = (leftStepsPerSec > 0) ? 100000 : -100000;
    stepperL.move(targetL); 
  }

  // 處理右輪（記得加上你前面抓到的右輪反向負號！）
  float adjustedRightSteps = -rightStepsPerSec; 
  if (adjustedRightSteps == 0) {
    stepperR.moveTo(stepperR.currentPosition());
  } else {
    stepperR.setMaxSpeed(abs(adjustedRightSteps));
    long targetR = (adjustedRightSteps > 0) ? 100000 : -100000;
    stepperR.move(targetR);
  }
}
void sendOdomToPC() {
  Serial.print("P");
  Serial.print(L_pulseCount);
  Serial.print(",");
  Serial.println(R_pulseCount);
}

// 編碼器中斷保持原樣...
void updateEncoderL() {
  static int lastA = LOW;
  int curA = digitalRead(L_encA);
  int curB = digitalRead(L_encB);
  if (curA != lastA) {
    (curA == HIGH) ? ((curB == LOW) ? L_pulseCount-- : L_pulseCount++) : ((curB == HIGH) ? L_pulseCount-- : L_pulseCount++);
  }
  lastA = curA;
}
void updateEncoderR() {
  static int lastA = LOW;
  int curA = digitalRead(R_encA);
  int curB = digitalRead(R_encB);
  if (curA != lastA) {
    (curA == HIGH) ? ((curB == LOW) ? R_pulseCount++ : R_pulseCount--) : ((curB == HIGH) ? R_pulseCount++ : R_pulseCount--);
  }
  lastA = curA;
}