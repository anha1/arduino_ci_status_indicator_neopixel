#include <Arduino.h>
#include <Adafruit_NeoPixel.h>
#include <SimpleTimer.h>

#define PIN         4
#define PIXELS      16
#define RUNNERS     2
#define PIXELS_PER_RUNNER 8

#define RUNNER_PIXELS     3
#define DETACHED_MILLIS 300000 // 5 minutes
#define MAX_COLOR 255
#define DEFAULT_BRIGHTNESS 5

#define MODE_BLUE 0 //detached (no commands for DETACHED_MILLIS)
#define MODE_GREEN 1 //ok
#define MODE_YELLOW 2 //warn
#define MODE_RED 3 //fail
//unexpected mode: white

#define SPEED_PARAM 12000

Adafruit_NeoPixel pixels = Adafruit_NeoPixel(PIXELS, PIN, NEO_GRB + NEO_KHZ800);

SimpleTimer timer;
long phase = 0;
long speed = 15;
int mode = MODE_BLUE;
int brightness = DEFAULT_BRIGHTNESS;
unsigned long lastCommand = 0;
unsigned long lastPhaseUpdate = 0;

int fromCommandValue(int commandValue) {
    return max(1, min(255, commandValue));
}

boolean isData() {
    return Serial.available() > 0;
}

void discardInput() {
    while (isData()) {        
        Serial.read();
        delay(1);
    }
}

void tryReadCommand() {
    if (!isData()) {
        return;
    }

    int newMode = fromCommandValue(Serial.parseInt());       
    int newSpeed = fromCommandValue(Serial.parseInt()); 
    int newBrightness = fromCommandValue(Serial.parseInt()); 

    discardInput();

    lastCommand = millis();
    mode = fromCommandValue(newMode);
    speed = fromCommandValue(newSpeed); 
    brightness = fromCommandValue(newBrightness);
}

boolean isDetached() {
  return (lastCommand == 0) || 
      ((millis() - lastCommand) > DETACHED_MILLIS);
}

boolean tryUpdatePhase() {

    int diff = millis() - lastPhaseUpdate;
    if (diff > (SPEED_PARAM / (speed + 1))) {
        phase++;        
        if (phase % PIXELS_PER_RUNNER == 0) {
            phase = 0;
        }
        lastPhaseUpdate = millis();
        return true;
    } else {
        return false;
    }
}

void tryDraw() {
  
  if (!tryUpdatePhase()) {
      return;
  }
  
  boolean isDetachedNow = isDetached();
  
  if (isDetachedNow) {
    brightness = DEFAULT_BRIGHTNESS;
    mode = MODE_BLUE;
  }  

  pixels.setBrightness(brightness);
  
  for (int i=0; i < RUNNERS; i++) {
          
    int red = 0;
    int green = 0;
    int blue = 0;    

    switch (mode) {
    case MODE_BLUE:
        blue = MAX_COLOR;
        break;
    case MODE_GREEN:
        green = MAX_COLOR;
        break;  
    case MODE_YELLOW:
        red = MAX_COLOR;
        green = MAX_COLOR;
        break;      
    case MODE_RED:
        red = MAX_COLOR;
        break;   
    default: 
        red = MAX_COLOR;
        green = MAX_COLOR;
        blue = MAX_COLOR;  
    }
    int index_disable = i * PIXELS_PER_RUNNER + phase ;
    int index_enable = (index_disable + RUNNER_PIXELS ) % PIXELS;
    pixels.setPixelColor(index_enable, pixels.Color(red, green, blue));  
    pixels.setPixelColor(index_disable, pixels.Color(0, 0, 0));  
  } 
  pixels.show();
}

void setup() {
  Serial.begin(9600);  
  pixels.begin();

  discardInput();
  timer.setInterval(16, tryDraw);
  timer.setInterval(500, tryReadCommand);
}

void loop() {
    timer.run();
}