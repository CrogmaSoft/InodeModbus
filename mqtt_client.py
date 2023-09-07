import time
import paho.mqtt.client as mqtt

current_state = ""

class mqtt_client:

    def __init__(self, config, mqtt_queue):
        mqtt_config = config["modbus_config"]["mqtt_config"]
        self.id = mqtt_config["mqtt_id"] + "_dev" if config["modbus_config"]["dev_mode"] else mqtt_config["mqtt_id"]
        self.user = mqtt_config["mqtt_user"]
        self.password = mqtt_config["mqtt_passwd"]
        self.server = mqtt_config["mqtt_broker"]
        self.port = mqtt_config["mqtt_port"]
        self.topic = ""
        self.payload = ""
        self.queue = mqtt_queue
        self._state = ""
        
    def on_connect(self, client, userdata, flags, rc):
        global current_state

        con_ref = "Connection refused:"
        if rc == 0:
            self._state = f"Connection to: {str(self.server)} successful"
        elif rc == 2:
            self._state = f"{con_ref} Invalid client ID"
        elif rc == 1:
            self._state = f"{con_ref} Invalid protocol version"
        elif rc == 3:
            self._state = f"{con_ref} Server not avaliable"
        elif rc == 4:
            self._state = f"{con_ref} Invalid user or password"
        elif rc == 5:
            self._state = f"{con_ref} Unauthorized connection"
        else:
            self._state = f"{con_ref} Unknown connection error"
        current_state = self._state
        return self._state

    def on_disconnect(self, client, userdata, flags, rc):
        global current_state
        self._state = f"Connection to: {str(self.server)}: terminated"
        current_state = self._state
        return self._state

    def on_message(self, client, userdata, msg):
        m = (msg.topic, msg.payload.decode("UTF-8"))
        self.queue.put(m)

    def on_subscribe(self, client, userdata, mid, state):
        self._state = "Subscribed to: " + str(mid)

    def on_publish(self, client, userdata, mid):
        self._state = "Publishing to: " + str(mid)

    def sub(self, topic):
        self.client.subscribe(topic, 0)

    def pub(self, topic, pay):
        self.client.publish(topic, pay)

    def run(self):
        self.client = mqtt.Client(client_id=self.id)
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        self.client.on_message = self.on_message
        self.client.on_publish = self.on_publish
        self.client.on_subscribe = self.on_subscribe
        self.client.username_pw_set(self.user, self.password)
        self.client.connect(self.server, self.port)
        self.client.loop_start()

    def stop(self):
        self.client.disconnect()
        self.client.loop_stop()

    def get_state():
        return current_state