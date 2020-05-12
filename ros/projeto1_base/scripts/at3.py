# -*- coding:utf-8 -*-
import cv2
import matplotlib.pyplot as plt
import numpy as np
import math
import time


pos_a_coef = []
neg_a_coef = []
pos_l_coef = []
neg_l_coef = []

def ponto_de_fuga(frame):

    xis = []
    yis = []

    mean_x = []
    mean_y = []

    ponto_de_fuga_x = []
    ponto_de_fuga_y = []

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

    edges = cv2.Canny(gray, 50, 150, apertureSize=3)
    ret, limiarizada = cv2.threshold(gray, 230, 255, cv2.THRESH_BINARY)
    lines = cv2.HoughLines(limiarizada,1, np.pi/180, 200)

    for x in range(0, len(lines)):    
        for rho, theta in lines[x]:
            a = np.cos(theta)
            b = np.sin(theta)


            if a > 0.4:
                pos_a_coef.append(a)
                pos_l_coef.append(b)
                x0 = a*rho
                y0 = b*rho
                x1 = int(x0 + 1000*(-b))
                y1 = int(y0 + 1000*(a))
                x2 = int(x0 - 1000*(-b))
                y2 = int(y0 - 1000*(a))
                line = cv2.line(frame,(x1,y1),(x2,y2),(0,255,0),3)

            elif a < -0.4:
                neg_a_coef.append(a)
                neg_l_coef.append(b)
                x0 = a*rho
                y0 = b*rho
                x3 = int(x0 + 1000*(-b))
                y3 = int(y0 + 1000*(a))
                x4 = int(x0 - 1000*(-b))
                y4 = int(y0 - 1000*(a))
                line = cv2.line(frame,(x3,y3),(x4,y4),(0,255,0),3)

                                
                try:
                    h1 = pos_l_coef[len(pos_l_coef)-1]
                    m1 = pos_a_coef[len(pos_a_coef)-1]

                    h2 = neg_l_coef[len(neg_l_coef)-1]
                    m2 = neg_a_coef[len(neg_a_coef)-1]
                    
                    xi = ((x1*y2 - y1*x2)*(x3 - x4) - (x1-x2)*(x3*y4 - y3*x4))/((x1-x2)*(y3-y4) - (y1-y2)*(x3-x4))
                    yi = ((x1*y2 - y1*x2)*(y3 - y4) - (y1-y2)*(x3*y4 - y3*x4))/((x1-x2)*(y3-y4) - (y1-y2)*(x3-x4))

                    xis.append(xi)
                    yis.append(yi)

                    ponto_de_fuga_x.append(xi)
                    ponto_de_fuga_y.append(yi)
                    
                except:
                    pass
            else:
                pass


    try:
        avg_x = int(np.mean(ponto_de_fuga_x))
        avg_y = int(np.mean(ponto_de_fuga_y))
        cv2.circle(frame, (avg_x,avg_y), 3, (255,0,0), 5)

    except:
        pass

    return (avg_x,avg_y)

