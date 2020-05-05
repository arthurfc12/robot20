#! /usr/bin/env python
# -*- coding:utf-8 -*-

from __future__ import print_function, division
import rospy
import numpy as np
import numpy
import tf
import math
import cv2
import time
from nav_msgs.msg import Odometry
from sensor_msgs.msg import Image, CompressedImage
from cv_bridge import CvBridge, CvBridgeError
from numpy import linalg
from tf import transformations
from tf import TransformerROS
import tf2_ros
from geometry_msgs.msg import Twist, Vector3, Pose, Vector3Stamped
from ar_track_alvar_msgs.msg import AlvarMarker, AlvarMarkers
from nav_msgs.msg import Odometry
from sensor_msgs.msg import Image
from std_msgs.msg import Header
from numpy import linalg
from tf import transformations
from tf import TransformerROS
import tf2_ros
import math
from geometry_msgs.msg import Twist, Vector3, Pose, Vector3Stamped
from ar_track_alvar_msgs.msg import AlvarMarker, AlvarMarkers
from nav_msgs.msg import Odometry
from sensor_msgs.msg import Image
from std_msgs.msg import Header

import visao_module


bridge = CvBridge()

cv_image = None
media = []
centro = []
atraso = 1.5E9 # 1 segundo e meio. Em nanossegundos

white_1_hsv = np.array([0, 0, 78], dtype=np.uint8)
white1 = np.array([200, 200, 200], dtype=np.uint8)
white_2_hsv = np.array([0, 0, 100], dtype=np.uint8)
white2 = np.array([255, 255, 255], dtype=np.uint8)


area = 0.0 # Variavel com a area do maior contorno

# Só usar se os relógios ROS da Raspberry e do Linux desktop estiverem sincronizados. 
# Descarta imagens que chegam atrasadas demais
check_delay = False 

resultados = [] # Criacao de uma variavel global para guardar os resultados vistos

x = 0
y = 0
z = 0 
id = 0

frame = "camera_link"
# frame = "head_camera"  # DESCOMENTE para usar com webcam USB via roslaunch tag_tracking usbcam

tfl = 0

tf_buffer = tf2_ros.Buffer()

def recebe(msg):
	global x # O global impede a recriacao de uma variavel local, para podermos usar o x global ja'  declarado
	global y
	global z
	global id
	for marker in msg.markers:
		id = marker.id
		marcador = "ar_marker_" + str(id)

		print(tf_buffer.can_transform(frame, marcador, rospy.Time(0)))
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



# A função a seguir é chamada sempre que chega um novo frame
def roda_todo_frame(imagem):
    print("frame")
    global cv_image
    global media
    global centro

    global resultados


    now = rospy.get_rostime()
    imgtime = imagem.header.stamp
    lag = now-imgtime # calcula o lag
    delay = lag.nsecs
    # print("delay ", "{:.3f}".format(delay/1.0E9))
    if delay > atraso and check_delay==True:
        print("Descartando por causa do delay do frame:", delay)
        return 
    try:
        antes = time.clock()
        cv_image = bridge.compressed_imgmsg_to_cv2(imagem, "bgr8")
        # Note que os resultados já são guardados automaticamente na variável
        # chamada resultados
        centro, imagem, resultados =  visao_module.processa(cv_image)        
        for r in resultados:
            # print(r) - print feito para documentar e entender
            # o resultado            
            pass

        depois = time.clock()
        # Desnecessário - Hough e MobileNet já abrem janelas
        #cv2.imshow("Camera", cv_image)
    except CvBridgeError as e:
        print('ex', e)
    
if __name__=="__main__":
    rospy.init_node("cor")

    topico_imagem = "/camera/rgb/image_raw/compressed"

    recebedor = rospy.Subscriber(topico_imagem, CompressedImage, roda_todo_frame, queue_size=4, buff_size = 2**24)
    recebedor = rospy.Subscriber("/ar_pose_marker", AlvarMarkers, recebe) # Para recebermos notificacoes de que marcadores foram vistos


    print("Usando ", topico_imagem)

    velocidade_saida = rospy.Publisher("/cmd_vel", Twist, queue_size = 1)

    tfl = tf2_ros.TransformListener(tf_buffer) #conversao do sistema de coordenadas 
    tolerancia = 25

    # Exemplo de categoria de resultados
    # [('chair', 86.965459585189819, (90, 141), (177, 265))]

    try:
        # Inicializando - por default gira no sentido anti-horário
        # vel = Twist(Vector3(0,0,0), Vector3(0,0,math.pi/10.0))
        
        while not rospy.is_shutdown():
            if cv_image is not None:

                mask_white = cv2.inRange(cv_image, white1, white2)

                blur = cv2.GaussianBlur(mask_white, (5,5),0)

                edges = cv2.Canny(blur,50,150)
                
                lines = cv2.HoughLines(edges,1,np.pi/180, 150)

                lista_m = []
                lista_h = []

                linhas_d_m = []
                linhas_d_x1 = []
                linhas_d_x2 = []
                linhas_d_y1 = []
                linhas_d_y2 = []
                linhas_d_h = []

                linhas_e_m = []
                linhas_e_x1 = []
                linhas_e_x2 = []
                linhas_e_y1 = []
                linhas_e_y2 = []
                linhas_e_h = []

                xis = []
                yis = []
                if lines is not None and len(lines) > 0 :
                    for x in range(0, len(lines)):    
                        for rho, theta in lines[x]:
                            a = np.cos(theta)
                            b = np.sin(theta)
                            x0 = a*rho
                            y0 = b*rho
                            x1 = int(x0 + 1000*(-b))
                            y1 = int(y0 + 1000*(a))
                            x2 = int(x0 - 1000*(-b))
                            y2 = int(y0 - 1000*(a))
                            m = (y2 - y1)/(x2 - x1)
                            
                            h = y1 - m*x1

                            lista_h.append(h)
                            lista_m.append(m)

                            #direita
                            if m>0.3 and m<2:
                                linhas_d_m.append(m)
                                linhas_d_x1.append(x1)
                                linhas_d_x2.append(x2)
                                linhas_d_y1.append(y1)
                                linhas_d_y2.append(y2)
                                linhas_d_h.append(h)


                            #esquerda
                            elif m<-0.2 and m>-2:
                                linhas_e_m.append(m)
                                linhas_e_x1.append(x1)
                                linhas_e_x2.append(x2)
                                linhas_e_y1.append(y1)
                                linhas_e_y2.append(y2)
                                linhas_e_h.append(h)
                            
                            else:
                                lista_m.remove(m) 
                                lista_h.remove(h)


            
        
                if len(lista_m) > 1 and lista_m[0] != lista_m[1]:
                    x_i = (lista_h[1] - lista_h[0])/(lista_m[0] - lista_m[1])
                    y_i = lista_m[0] * x_i + lista_h[0]
                    x_i = int(x_i)
                    y_i = int(y_i)
                    xis.append(x_i)
                    yis.append(y_i)

            
                x1 = 0
                x2 = 0
                x3 = 0
                x4 = 0
                y1 = 0
                y2 = 0
                y3 = 0
                y4 = 0
                
                #linha direita
                if len(linhas_d_m)>1:
                            x1 = int(np.mean(linhas_d_x1))
                            x2 = int(np.mean(linhas_d_x2))
                            y1 = int(np.mean(linhas_d_y1))
                            y2 = int(np.mean(linhas_d_y2))
                            cv2.line(frame,(x1,y1), (x2,y2), (50,0,255),2) 
                
                #linha esquerda
                if len(linhas_e_m)>1:
                            x3 = int(np.mean(linhas_e_x1))
                            x4 = int(np.mean(linhas_e_x2))
                            y3 = int(np.mean(linhas_e_y1))
                            y4 = int(np.mean(linhas_e_y2))
                            cv2.line(frame,(x3,y3), (x4,y4), (50,0,255),2) 

                #ponto de intersecção
                if x1!=0 and x2!=0 and x3!=0 and x4!=0:
                    px = int(((x1*y2 - y1*x2)*(x3-x4) - (x1-x2)*(x3*y4 - y3*x4))/((x1-x2)*(y3-y4) - (y1-y2)*(x3-x4)))
                    py = int(((x1*y2 - y1*x2)*(y3-y4) - (y1-y2)*(x3*y4-x4*y3))/((x1-x2)*(y3-y4)-(y1-y2)*(x3-x4)))
                    cv2.circle(frame, (px, py), 1, (0,255,0), 5)

                for r in resultados:
                    print(r)
            #velocidade_saida.publish(vel)
            rospy.sleep(0.1)

    except rospy.ROSInterruptException:
        print("Ocorreu uma exceção com o rospy")