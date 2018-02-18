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


#define MODE_BLUE 0 //detached (no commands for DETACHED_MILLIS)
#define MODE_GREEN 1 //ok
#define MODE_YELLOW 2 //warn
#define MODE_RED 3 //fail
//unexpected mode: white

#define ANIMATION_DELAY_MIN_MS 30
#define ANIMATION_DELAY_MAX_MS 5000

#define BRIGHTNESS_DEFAULT 1
#define COMMAND_MIN 0
#define COMMAND_MAX 255

Adafruit_NeoPixel pixels = Adafruit_NeoPixel(PIXELS, PIN, NEO_GRB + NEO_KHZ800);

SimpleTimer timer;
int phase = 0;

int mode = MODE_BLUE;

int brightness = BRIGHTNESS_DEFAULT;
unsigned long lastCommand = 0;
unsigned long lastPhaseUpdate = 0;

int targetAnimationDelayMs = ANIMATION_DELAY_MAX_MS;

int fromCommandValue(int commandValue) {
    return max(COMMAND_MIN, min(COMMAND_MAX, commandValue));
}

boolean isData() {
    return Serial.available() > 0;
}

void discardInput() {
    while (isData()) {        
        Serial.read();
    }
}

int getTargetAnimationDelayMs(int speed) {
    long diffDelayMs = (ANIMATION_DELAY_MAX_MS - ANIMATION_DELAY_MIN_MS);
    long diffCommand = (COMMAND_MAX - speed) ;    
    long addMs = diffDelayMs * diffCommand / COMMAND_MAX;
    return ANIMATION_DELAY_MIN_MS + addMs;
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
    targetAnimationDelayMs = getTargetAnimationDelayMs(newSpeed);
    brightness = fromCommandValue(newBrightness);
}

boolean isDetached() {
  return (lastCommand == 0) || 
      ((millis() - lastCommand) > DETACHED_MILLIS);
}

boolean tryUpdatePhase() {
    int animationDelayMs = millis() - lastPhaseUpdate;
    
    if (animationDelayMs >= targetAnimationDelayMs) {
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
    mode = MODE_BLUE;
    targetAnimationDelayMs = ANIMATION_DELAY_MAX_MS;
    brightness = BRIGHTNESS_DEFAULT;
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
  timer.setInterval(1, tryDraw);
  timer.setInterval(100, tryReadCommand);
}

void loop() {
    timer.run();
}