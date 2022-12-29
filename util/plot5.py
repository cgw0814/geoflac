#!/usr/bin/env python

import sys, os
import numpy as np

import flac
import flac_interpolate as fi
import flac_gravity3 as fg


# domain bounds
left = -200
right = 250
up = 10
down = -200
dx = 4
dz = 1.5

def find_trench_index(z):
    '''Returns the i index of trench location.'''
    zz = z[:,0]
    # the highest point defines the forearc
    imax = zz.argmax()
    # the trench is the lowest point west of forearc
    i = zz[:imax].argmin()
    return i


def interpolate_sII(frame, xtrench):
    # domain bounds in km
    fi.xmin = xtrench + left
    fi.xmax = xtrench + right
    fi.zmin = down
    fi.zmax = up

    # resolution in km
    fi.dx = dx
    fi.dz = dz

    xx, zz, ph = fi.interpolate(frame, 'sII')
    return xx, zz, ph


###############################################

frame = int(sys.argv[1])

fl = flac.Flac()
x, z = fl.read_mesh(frame)

itrench = find_trench_index(z)
xtrench = x[itrench,0]

# get interpolated phase either from previous run or from original data
stressfile = 'intp3-sII.%d' % frame
if not os.path.exists(stressfile):
    xx, zz, ph = interpolate_sII(frame, xtrench)
    f = open(stressfile, 'w')
    f.write('%d %d\n' % xx.shape)
    flac.printing(xx, zz, ph, stream=f)
    f.close()
else:
    f = open(stressfile)
    nx, nz = np.fromfile(f, sep=' ', count=2)
    str = np.fromfile(f, sep=' ')
    str.shape = (nx, nz, 3)
    xx = str[:,:,0]
    zz = str[:,:,1]
    ph = str[:,:,2]
    f.close()


 # get interpolated T either from previous run or from original data
tfile = 'intp3-T.%d' % frame
if not os.path.exists(tfile):
    T = fl.read_temperature(frame)
    f = open(tfile, 'w')
    f.write('%d %d\n' % x.shape)
    flac.printing(x, z, T, stream=f)
    f.close()
else:
    f = open(tfile)
    nx, nz = np.fromfile(f, sep=' ', count=2)
    tmp = np.fromfile(f, sep=' ')
    tmp.shape = (nx, nz, 3)
    T = tmp[:,:,2]
    f.close()


# get topography and gravity at uniform spacing
px, topo, topomod, gravity = fg.compute_gravity2(frame)
# convert to km and mGal before saving
px *= 1e-3
topo *= 1e-3
topomod *= 1e-3
gravity *= 1e5
gfile = 'topo-grav.%d' % frame
f = open(gfile, 'w')
flac.printing(px, topo, gravity, topomod, stream=f)
f.close()


###############
model = os.path.split(os.getcwd())[-1]
psfile = 'result3.%d.ps' % frame
pngfile = 'result3.%d.png' % frame
strgrd = 'stress3.%d.grd' % frame
tgrd = 'temperature3.%d.grd' % frame
strain_ratecpt = '/home/summer-tan2/flac/util/stress.cpt'

xmin = xtrench + left
xmax = xtrench + right
zmin = down
zmax = up
aspect_ratio = float(up - down) / (right - left)
width = 6.5
height = width * aspect_ratio
shiftz = height + 0.3

# height of gravity plot
height2 = 1.0

# gravity grid
gravgridsize = 50
gmin = int(gravity.min() / gravgridsize - 1) * gravgridsize
gmax = int(gravity.max() / gravgridsize + 1) * gravgridsize
gravann = max(abs(gmin), abs(gmax))
# topography grid
topogridsize = 2
tpmin = int(topo.min() / topogridsize - 1) * topogridsize
tpmax = int(topo.max() / topogridsize + 1) * topogridsize
topoann = max(abs(tpmin), abs(tpmax))
# interval of temperature contours
cint = 200

if not os.path.exists(strgrd):
    cmd = 'tail -n +2 %(stressfile)s | xyz2grd -G%(strgrd)s -I%(dx)f/%(dz)f -R%(xmin)f/%(xmax)f/%(zmin)f/%(zmax)f' % locals()
    #print(cmd)
    os.system(cmd)

if not os.path.exists(tgrd):
    cmd = 'tail -n +2 %(tfile)s | surface -G%(tgrd)s -Ll0 -I%(dx)f/%(dz)f -R%(xmin)f/%(xmax)f/%(zmin)f/%(zmax)f' % locals()
    #print(cmd)
    os.system(cmd)

cmd = '''
rm -f .gmtcommands* .gmtdefaults*

gmtset MEASURE_UNIT = inch
gmtset LABEL_FONT_SIZE=14 ANNOT_FONT_SIZE_PRIMARY=10

# axis annotation
psbasemap -JX%(width)f/%(height)f -Ba100f10/a20f5::WSne -R%(left)f/%(right)f/%(zmin)f/%(zmax)f -X0.9 -Y4 -P -K > %(psfile)s

# phase plot
grdimage %(strgrd)s -C%(strain_ratecpt)s -R%(xmin)f/%(xmax)f/%(zmin)f/%(zmax)f -J -P -O -K >> %(psfile)s

# temperature contours
grdcontour %(tgrd)s -C%(cint)f -A200 -W1p -J -R -P -K -O >> %(psfile)s

# baseline plot
psxy -JX%(width)f/%(height2)f -R%(xmin)f/%(xmax)f/-1/1 -A -Wthin,0,. -Y%(shiftz)f -P -K -O <<END>> %(psfile)s
%(xmin)f 0
%(xmax)f 0
END

# gravity plot
color=red
cut -f1,3 %(gfile)s | \
psxy -JX%(width)f/%(height2)f -R%(xmin)f/%(xmax)f/-%(gravann)f/%(gravann)f -B/a%(gravann)ff%(gravgridsize)f:"@;$color;mGal@;;":E -A -Wthin,$color -P -K -O >> %(psfile)s

# topography plot
color=blue
cut -f1,2 %(gfile)s | \
psxy -JX%(width)f/%(height2)f -R%(xmin)f/%(xmax)f/-%(topoann)f/%(topoann)f -B/a%(topoann)ff%(topogridsize)f:"@;$color;km@;;":W -A -Wthin,$color -P -K -O >> %(psfile)s
cut -f1,4 %(gfile)s | \
psxy -J -R -A -Wthin,$color,-- -P -K -O >> %(psfile)s

echo %(xmin)f %(topogridsize)d 14 0 1 LB "Model=%(model)s   Frame=%(frame)d   Trench location=%(xtrench).3f km" | \
pstext -D0/1 -N -J -R -P -O >> %(psfile)s

convert -density 150 %(psfile)s %(pngfile)s
''' % locals()
#print(cmd)
os.system(cmd)
