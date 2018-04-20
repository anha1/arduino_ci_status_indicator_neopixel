import serial
import logging
import os

class CiNeopixelController:
    
    def __init__(self, config): 
        self.config = config
        self.device = self.open_controller()
       

    def get_tty_device(self):
        for device in os.listdir('/dev/'):
            if device.startswith('ttyUSB'):
                return '/dev/' + device

        raise Exception('Cant detect NeoPixel Controler')

    def open_controller(self):
        tty = self.get_tty_device()
        logging.info('Using serial: %s' % tty)

        # Arduino restarts on this operation, so serial should be always opened
        logging.info('Trying to open a controller')
        return serial.Serial(
            port=tty,
            baudrate=self.config['indicator'].getint('baudrate'),
            timeout=self.config['indicator'].getint('write_timeout_seconds'))

    def set_mode(self, mode, speed, brightness):
        command = '%d %d %d;' % (mode, speed, brightness)
        logging.debug('Command: %s' % command)
        if self.device:
            self.device.write(command.encode())

    def get_command_val(self, seconds, min_val, max_val, reach_max_val_hours):
        reach_max_val_seconds = 3600. * reach_max_val_hours
        val = max_val * (seconds/reach_max_val_seconds)
        return max(min_val, min(max_val, int(val)))


    def is_warn(self, failed_seconds):
        return failed_seconds < (self.config['warn'].getint('warn_before_fail_hours') * 3600)


    def get_speed(self, seconds):
        return self.get_command_val(seconds=seconds,
                            min_val=self.config['fail'].getint('min_speed'),
                            max_val=self.config['fail'].getint('max_speed'),
                            reach_max_val_hours=self.config['fail'].getint('max_speed_reached_hours'))


    def get_fail_brightness(self, failed_seconds):
        return self.get_command_val(seconds=failed_seconds,
                            min_val=self.config['fail'].getint('min_brightness'),
                            max_val=self.config['fail'].getint('max_brightness'),
                            reach_max_val_hours=self.config['fail'].getint('max_brightness_reached_hours'))

    def set_seconds_failed(self, max_failed_seconds):
        speed = self.get_speed(abs(max_failed_seconds))
        if max_failed_seconds > 0:
            if self.is_warn(max_failed_seconds):
                self.set_mode(mode=2,
                        speed=speed,
                        brightness=1)
                logging.debug('Final status: WARN')
            else:
                self.set_mode(mode=3,
                        speed=speed,
                        brightness=self.get_fail_brightness(max_failed_seconds))
                logging.debug('Final status: FAIL')
        else:
            logging.debug('Final status: OK')
            self.set_mode(mode=1,
                    speed=speed,
                    brightness=1)

    def set_disconnected(self):
        self.set_mode(mode=4,
                      speed=255,
                      brightness=50)              
