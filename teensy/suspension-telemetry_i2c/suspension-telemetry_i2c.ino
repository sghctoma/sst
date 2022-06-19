#include <SPI.h>
#include <SD.h>
#include <MTP.h>
#include <SSD1306Ascii.h>
#include <SSD1306AsciiSoftSpi.h>
#include <Wire.h>
#include <AS5600.h>

//--------------------------------------------------
// Rotary encoder
AMS_5600 ams5600_front(&Wire);
AMS_5600 ams5600_rear(&Wire1);
bool have_front = false;
bool have_rear = false;

//--------------------------------------------------
// OLED display
#define SSD1306_CS_PIN    5
#define SSD1306_DC_PIN    6
#define SSD1306_RST_PIN   7
#define SSD1306_MOSI_PIN  8
#define SSD1306_CLK_PIN   9

SSD1306AsciiSoftSpi oled;

//--------------------------------------------------
// MTP
#define SD_STR  "sd1"
#define SD_CS   10
#define SPI_SPEED SD_SCK_MHZ(16)

SDClass sdx;
MTPStorage_SD storage;
MTPD    mtpd(&storage);
bool mtp_mode;

//--------------------------------------------------
// Logging
File file;
IntervalTimer collectionTimer;

struct record {
  uint32_t micros;
  uint16_t frontAngle;
  uint16_t rearAngle;
};

#define BUFFER_SIZE 2048
record dataBuffer1[BUFFER_SIZE];
record dataBuffer2[BUFFER_SIZE];
record *busyBuffer = dataBuffer1;
record *nextbuffer = dataBuffer2;
record *readyBuffer = NULL;
uint16_t count = 0;

//--------------------------------------------------
// Setup functions

void setup_display() {
  oled.begin(&Adafruit128x32, SSD1306_CS_PIN, SSD1306_DC_PIN, SSD1306_CLK_PIN, SSD1306_MOSI_PIN, SSD1306_RST_PIN);
  oled.setFont(System5x7);
  oled.set2X();
  oled.clear();
}

void setup_ams5600() {
  oled.println("NO MAGNET");

  Wire.begin();
  Wire.setClock(1000000);
  Wire1.begin();
  Wire1.setClock(1000000);
  while (!((ams5600_front.isConnected() && ams5600_front.detectMagnet() == 1) ||
           (ams5600_rear.isConnected() && ams5600_rear.detectMagnet() == 1))) {
    delay(1000);
  }

  oled.clear();
  
  if (ams5600_front.isConnected() && ams5600_front.detectMagnet() == 1) {
    have_front = true;
    
    // Set current angle as 0, and max angle to 180 degrees
    word baseline = 0;
    for (int i = 0; i < 10; ++i) {
      baseline += ams5600_front.getRawAngle();
      delay(100);
    }
    baseline = baseline / 10;
    ams5600_front.setStartPosition(baseline);
    ams5600_front.setMaxAngle(2048);

    oled.println(" FORK  OK ");
  } else {
    oled.println(" FORK  NO ");
  }

  if (ams5600_rear.isConnected() && ams5600_rear.detectMagnet() == 1) {
    have_rear = true;
    
    // Set current angle as 0, and max angle to 180 degrees
    word baseline = 0;
    for (int i = 0; i < 10; ++i) {
      baseline += ams5600_rear.getRawAngle();
      delay(100);
    }
    baseline = baseline / 10;
    ams5600_rear.setStartPosition(baseline);
    ams5600_rear.setMaxAngle(2048);
  
    oled.println(" SHOCK OK ");
  } else {
    oled.println(" SHOCK NO ");
  }
}

bool setup_mtp() {
  pinMode(SD_CS ,OUTPUT);
  digitalWriteFast(SD_CS, HIGH);
  if (sdx.sdfs.begin(SdSpiConfig(SD_CS, SHARED_SPI, SPI_SPEED))) {
    storage.addFilesystem(sdx, SD_STR);
    return true;
  }
  
  return false;
}

bool setup_sd() {
  if (!SD.begin(10)) {
    return false;
  }

  unsigned short index;
  File indexFile = SD.open("INDEX", FILE_READ);
  if (indexFile) {
    byte buf[2];
    indexFile.read(buf, 2);
    index = ((buf[0] << 8) | buf[1]) + 1;
  } else {
    index = 0;
  }
  indexFile.close();

  indexFile = SD.open("INDEX", FILE_WRITE);
  if (indexFile) {
    indexFile.seek(0);
    indexFile.write((byte)(index >> 8));
    indexFile.write((byte)(index & 0xFF));
    indexFile.close();
  } else {
    return false;
  }

  char filename[10];
  sprintf(filename, "%05u.SST", index);
  file = SD.open(filename, FILE_WRITE);
  
  return true;
}

void setup() {
  setup_display();
  
  delay(500);
  if (usb_configuration) {
    mtp_mode = true;
    if (setup_mtp()) {
      oled.clear();
      oled.println(" MTP MODE ");
    } else {
      oled.clear();
      oled.println(" MTP ERROR");
      while(1);
    }
  } else {
    setup_ams5600();
    if (!setup_sd()) {
      oled.clear();
      oled.println(" SD ERROR ");
      while(1);
    }
    
   collectionTimer.begin(collect, 200); 
  }
}

//--------------------------------------------------
// ISR
void collect() {
  if (++count == BUFFER_SIZE) {
    count = 0;
    readyBuffer = busyBuffer;
    busyBuffer = nextbuffer;
    nextbuffer = readyBuffer;
  }
  
  busyBuffer[count].micros = micros();
  if (have_front) {
    busyBuffer[count].frontAngle = ams5600_front.getScaledAngle();
  } else {
    busyBuffer[count].frontAngle = 0xFFFF;
  }

  if (have_rear) {
    busyBuffer[count].rearAngle = ams5600_rear.getScaledAngle();
  } else {
    busyBuffer[count].rearAngle = 0xFFFF;
  }
}

//--------------------------------------------------
// Main loop

void loop() {
  if (mtp_mode) {
    mtpd.loop();
    return;
  }

  if (NULL != readyBuffer) {
    file.write(readyBuffer, sizeof(record)*BUFFER_SIZE);
    file.flush();
    
    readyBuffer = NULL;
  }
  delay(1);
}
