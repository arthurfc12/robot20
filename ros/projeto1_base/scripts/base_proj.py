#! /usr/bin/env python
# -*- coding:utf-8 -*-

from __future__ import print_function, division
import rospy
import numpy as np
from numpy import linalg
from tf import transformations
from tf import TransformerROS
import tf2_ros
import cv2
import math
from geometry_msgs.msg import Twist, Vector3, Pose, Vector3Stamped
from ar_track_alvar_msgs.msg import AlvarMarker, AlvarMarkers
from nav_msgs.msg import Odometry
from sensor_msgs.msg import Image, CompressedImage
from std_msgs.msg import Header
from sensor_msgs.msg import LaserScan
from cv_bridge import CvBridge, CvBridgeError
import cor_module
import time
import visao_module
import at3

#Os três creepers(gravar vídeo para cada um dos goals p cada rubrica)
#goal1 = ("blue", 11, "cat")
#goal2 = ("green",21,"dog")
#goal3 = ("pink",12,"bike")

area = 0.0 # Variavel com a area do maior contorno

# Só usar se os relógios ROS da Raspberry e do Linux desktop estiverem sincronizados. 
# Descarta imagens que chegam atrasadas demais
check_delay = False 

resultados = [] # Criacao de uma variavel global para guardar os resultados vistos

leitura_scan = 0
x = 0
y = 0
z = 0 
id = 0

linear = 0.15
angular = 0.15

frame = "camera_link"
# frame = "head_camera"  # DESCOMENTE para usar com webcam USB via roslaunch tag_tracking usbcam

tfl = 0

tf_buffer = tf2_ros.Buffer()
bridge = CvBridge()

cv_image = None
media = []
centro = []
atraso = 1.5E9 # 1 segundo e meio. Em nanossegundos
image_cor = None


# A função a seguir é chamada sempre que chega um novo frame
def roda_todo_frame(imagem):
    print("frame")
    global cv_image
    global media
    global centro
    global image_cor
    global resultados
    global area


    now = rospy.get_rostime()
    imgtime = imagem.header.stamp
    lag = now-imgtime # calcula o lag
    delay = lag.nsecs
    # print("delay ", "{:.3f}".format(delay/1.0E9))
    '''if delay > atraso and check_delay==True:
        print("Descartando por causa do delay do frame:", delay)
        return''' 
    try:
        antes = time.clock()
        cv_image2 = bridge.compressed_imgmsg_to_cv2(imagem, "bgr8")
        # Note que os resultados já são guardados automaticamente na variável
        # chamada resultados
        centro, output_net, resultados =  visao_module.processa(cv_image2)        
        for r in resultados:
            # print(r) - print feito para documentar e entender
            # o resultado            
            pass

        media, centro, image_cor, area = visao_module.identifica_cor(cv_image2) 


        depois = time.clock()
        cv_image = output_net.copy()
        # Desnecessário - Hough e MobileNet já abrem janelas
    except CvBridgeError as e:
        print('ex', e)

def scaneou(dado):
    global leitura_scan
    leitura_scan = np.array(dado.ranges[0]).round(decimals=2)

def recebe(msg):
    global x # O global impede a recriacao de uma variavel local, para podermos usar o x global ja'  declarado
    global y
    global z
    global id
    for marker in msg.markers:
        id = marker.id
        marcador = "ar_marker_" + str(id)

        #print(tf_buffer.can_transform(frame, marcador, rospy.Time(0)))
        header = Header(frame_id=marcador)
        # Procura a transformacao em sistema de coordenadas entre a base do robo e o marcador numero 100
        # Note que para seu projeto 1 voce nao vai precisar de nada que tem abaixo, a 
        # Nao ser que queira levar angulos em conta
        trans = tf_buffer.lookup_transform(frame, marcador, rospy.Time(0))
        
        # Separa as translacoes das rotacoes
        x = trans.transform.translation.x
        y = trans.transform.translation.y
        z = trans.transform.translation.z
        # ATENCAO: tudo o que vem a seguir e'  so para calcular um angulo
        # Para medirmos o angulo entre marcador e robo vamos projetar o eixo Z do marcador (perpendicular) 
        # no eixo X do robo (que e'  a direcao para a frente)
        t = transformations.translation_matrix([x, y, z])
        # Encontra as rotacoes e cria uma matriz de rotacao a partir dos quaternions
        r = transformations.quaternion_matrix([trans.transform.rotation.x, trans.transform.rotation.y, trans.transform.rotation.z, trans.transform.rotation.w])
        m = numpy.dot(r,t) # Criamos a matriz composta por translacoes e rotacoes
        z_marker = [0,0,1,0] # Sao 4 coordenadas porque e'  um vetor em coordenadas homogeneas
        v2 = numpy.dot(m, z_marker)
        v2_n = v2[0:-1] # Descartamos a ultima posicao
        n2 = v2_n/linalg.norm(v2_n) # Normalizamos o vetor
        x_robo = [1,0,0]
        cosa = numpy.dot(n2, x_robo) # Projecao do vetor normal ao marcador no x do robo
        angulo_marcador_robo = math.degrees(math.acos(cosa))

        # Terminamos
        print("id: {} x {} y {} z {} angulo {} ".format(id, x,y,z, angulo_marcador_robo))



creeper_found = False
faixa_fuga= 20
faixa_creeper = 20
dist_creeper = 0.40
creeper_caught = False
dist_base = 0.22



################### definir velocidades #############################

def stop():
    vel = Twist(Vector3(0,0,0), Vector3(0,0,0))
    return vel

def re(linear):
    vel = Twist(Vector3(-linear,0,0), Vector3(0,0,0))
    return vel

def find_pista(angular):
    vel = Twist(Vector3(0,0,0), Vector3(0,0,-angular))
    return vel

def andar_pista(centro_robot, ponto_fuga, faixa_fuga, linear, angular):
        #esquerda
        if ponto_fuga - faixa_fuga > centro_robot:
            vel = Twist(Vector3(0,0,0), Vector3(0,0,-angular))

        #direita
        elif ponto_fuga + faixa_fuga < centro_robot:
            vel = Twist(Vector3(0,0,0), Vector3(0,0,angular))

        #frente
        if abs(ponto_fuga - centro_robot) <= faixa_fuga:
            vel = Twist(Vector3(linear,0,0), Vector3(0,0,0))

        return vel
    
def find_creeper(centro_creeper, centro_robot, faixa_creeper, linear, angular):
        #esquerda não achado
        if centro_creeper - faixa_creeper > centro_robot:
            vel = Twist(Vector3(0,0,0), Vector3(0,0,-angular))
        #direita não achado
        elif centro_creeper + faixa_creeper < centro_robot:
            vel = Twist(Vector3(0,0,0), Vector3(0,0,angular))
        #frente achado
        if abs(centro_creeper - centro_robot) <= faixa_creeper:
            vel = Twist(Vector3(linear,0,0), Vector3(0,0,0))
        return vel
    
     

################ LOOP PRINCIPAL ########################
if __name__=="__main__":
    rospy.init_node("base_proj")

    topico_imagem = "/camera/rgb/image_raw/compressed"

    recebedor2 = rospy.Subscriber(topico_imagem, CompressedImage, roda_todo_frame, queue_size=4, buff_size = 2**24)
    recebedor = rospy.Subscriber("/ar_pose_marker", AlvarMarkers, recebe) # Para recebermos notificacoes de que marcadores foram vistos


    velocidade_saida = rospy.Publisher("/cmd_vel", Twist, queue_size = 1)
    recebe_scan = rospy.Subscriber("/scan", LaserScan, scaneou)

    tfl = tf2_ros.TransformListener(tf_buffer) #conversao do sistema de coordenadas 
    #tolerancia = 25

    # Exemplo de categoria de resultados
    # [('chair', 86.965459585189819, (90, 141), (177, 265))]
    vel = Twist(Vector3(0,0,0), Vector3(0,0,0)) #Começa parado
    try:        
        while not rospy.is_shutdown():
            if cv_image is not None:
                try:
                    ponto_fuga = at3.ponto_de_fuga(cv_image)
                except:
                    pass

                if len(centro) and len(media) != 0:
                    if creeper_found == False and area >= 1000:
                        vel = find_creeper(centro[0], media[0], faixa_creeper, linear, angular)
                    else:
                        vel = andar_pista(centro[0],ponto_fuga[0], faixa_fuga, linear, angular)

                    if leitura_scan <= dist_creeper:
                        vel = stop()
                        creeper_found = True
                        #ACESSAR GARRA
                        leitura = raw_input()
                    if creeper_caught == True:
                        vel = find_pista(angular)
                        if area <= 1000:
                            vel = andar_pista(centro[0],ponto_fuga[0], faixa_fuga, linear, angular)
                            if base_found == False:
                                vel = find_base(centro[0], media[0], faixa_creeper, linear, angular)
                            else:
                                vel = andar_pista(centro[0],ponto_fuga[0], faixa_fuga, linear, angular)
                            
                            if leitura_scan <= dist_base:
                                vel = stop()
                                base_found = True
                                #ACESSAR GARRA
                                leitura = raw_input()

                velocidade_saida.publish(vel)


                cv2.imshow("Camera", cv_image)
                cv2.waitKey(1)
                if image_cor is not None:
                    cv2.imshow("Debug", image_cor) 
                    cv2.waitKey(1)
                else: 
                    print("debug nulo")

                rospy.sleep(0.1)
    except rospy.ROSInterruptException:
        print("Ocorreu uma exceção com o rospy")