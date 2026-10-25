# Control del ELEGOO Smart Robot Car V4.0 por WiFi
#
# Antes de correr esto:
#   1. Prende el robot.
#   2. Conecta la computadora al WiFi del robot (se llama "ELEGOO-xxxx").
#   3. Corre:  python3 Main.py

import socket
import threading
import time

ROBOT_IP = "192.168.4.1"
ROBOT_PUERTO = 100

# Direcciones que entiende el robot
IZQUIERDA = 1
DERECHA = 2
ADELANTE = 3
ATRAS = 4


class Robot:
    def __init__(self):
        print("Conectando al robot...")
        self.conexion = socket.create_connection((ROBOT_IP, ROBOT_PUERTO), timeout=5)
        self.conexion.settimeout(None)
        self.respuestas = []
        self.contador = 0
        self.angulo = None
        # El robot manda {Heartbeat} cada segundo y hay que contestarle,
        # si no, nos desconecta. Esto lo hace un hilo en segundo plano.
        threading.Thread(target=self._escuchar, daemon=True).start()
        print("¡Conectado!")

    def _escuchar(self):
        buffer = ""
        while True:
            datos = self.conexion.recv(1024)
            if not datos:
                print("El robot se desconectó")
                return
            buffer += datos.decode(errors="ignore")
            # Separar los mensajes {...} que llegaron
            while "}" in buffer:
                mensaje, buffer = buffer.split("}", 1)
                mensaje = mensaje[mensaje.find("{") + 1:]
                if mensaje == "Heartbeat":
                    self.conexion.sendall(b"{Heartbeat}")
                else:
                    self.respuestas.append(mensaje)

    def _enviar(self, comando):
        self.contador += 1
        etiqueta = str(self.contador)
        texto = '{"H":"' + etiqueta + '"' + comando + "}"
        self.conexion.sendall(texto.encode())
        return etiqueta

    def _esperar_respuesta(self, etiqueta, espera=2):
        limite = time.time() + espera
        while time.time() < limite:
            for r in list(self.respuestas):
                if r.startswith(etiqueta + "_"):
                    self.respuestas.remove(r)
                    return r[len(etiqueta) + 1:]
            time.sleep(0.02)
        return None

    # ---------- Comandos sencillos ----------

    def mover(self, direccion, velocidad=150, milisegundos=1000):
        """Mueve el robot por un tiempo y luego se detiene solo. Velocidad: 0 a 255."""
        self._enviar(f',"N":2,"D1":{direccion},"D2":{velocidad},"T":{milisegundos}')
        time.sleep(milisegundos / 1000)

    def avanzar_sin_parar(self, velocidad=150):
        """Empieza a avanzar y sigue avanzando hasta que llames a parar()."""
        self._enviar(f',"N":3,"D1":{ADELANTE},"D2":{velocidad}')

    def adelante(self, velocidad=150, milisegundos=1000):
        self.mover(ADELANTE, velocidad, milisegundos)

    def atras(self, velocidad=150, milisegundos=1000):
        self.mover(ATRAS, velocidad, milisegundos)

    def izquierda(self, velocidad=100, milisegundos=500):
        self.mover(IZQUIERDA, velocidad, milisegundos)

    def derecha(self, velocidad=100, milisegundos=500):
        self.mover(DERECHA, velocidad, milisegundos)

    def parar(self):
        self._enviar(',"N":100')

    def mirar(self, angulo):
        """Gira la cabeza (sensor ultrasónico). 90 = al frente, 10 = derecha, 170 = izquierda."""
        if angulo == self.angulo:
            return  # ya está mirando ahí, no hace falta esperar
        self._enviar(f',"N":5,"D1":1,"D2":{angulo}')
        self.angulo = angulo
        time.sleep(0.5)

    def distancia(self):
        """Devuelve cuántos centímetros hay hasta el obstáculo de enfrente."""
        etiqueta = self._enviar(',"N":21,"D1":2')
        respuesta = self._esperar_respuesta(etiqueta)
        if respuesta is None or not respuesta.isdigit():
            return None
        return int(respuesta)

    def cerrar(self):
        self.parar()
        self.conexion.close()


# ---------- Aquí escribes lo que quieres que haga el robot ----------

# Ajustes del laberinto (cámbialos si hace falta)
DISTANCIA_LIBRE = 20   # cm: si hay más que esto, el camino está libre
VELOCIDAD = 100       # velocidad para avanzar (0 a 255)
MEDIR_CADA_MS = 50     # cada cuánto mide la distancia mientras avanza
VELOCIDAD_GIRO = 100   # velocidad para girar
GIRO_90_MS = 200       # cuánto tiempo tarda en girar 90 grados (calíbralo)

# Hacia dónde mira la cabeza
FRENTE = 90
LADO_DERECHO = 10
LADO_IZQUIERDO = 170


def hay_espacio(robot, angulo):
    """Mira hacia un lado y dice si el camino está libre."""
    robot.mirar(angulo)
    cm = robot.distancia()
    print("  mirando", angulo, "->", cm, "cm")
    if cm is None:
        return False  # si no pude leer el sensor, mejor no arriesgarse
    if cm == 0:
        return False  # 0 puede significar que la pared está pegadita al sensor
    return cm > DISTANCIA_LIBRE


if __name__ == "__main__":
    robot = Robot()
    try:
        # Busca la salida del laberinto. Presiona Ctrl + C para detenerlo.
        # Orden: primero adelante, luego derecha, luego izquierda, y si no, atrás.
        avanzando = False
        while True:
            if hay_espacio(robot, FRENTE):
                # Sigue avanzando sin frenar mientras mide la distancia
                if not avanzando:
                    print("Adelante")
                    robot.avanzar_sin_parar(VELOCIDAD)
                    avanzando = True
                time.sleep(MEDIR_CADA_MS / 1000)
                continue

            robot.parar()
            avanzando = False
            print("¡Obstáculo! Buscando otro camino...")

            if hay_espacio(robot, LADO_DERECHO):
                print("Giro a la derecha")
                robot.derecha(VELOCIDAD_GIRO, GIRO_90_MS)
            elif hay_espacio(robot, LADO_IZQUIERDO):
                print("Giro a la izquierda")
                robot.izquierda(VELOCIDAD_GIRO, GIRO_90_MS)
            else:
                print("Callejón sin salida, me doy la vuelta")
                robot.derecha(VELOCIDAD_GIRO, GIRO_90_MS * 2)

            robot.mirar(FRENTE)
    except KeyboardInterrupt:
        print("Detenido")
    finally:
        robot.cerrar()
