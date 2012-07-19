import sys
from numbers import Complex
import operator
from math import log
import functools
import array
import collections
import time

if sys.platform == "win32":
    # Attempt to configure Tcl/Tk without requiring PATH
    import FixTk
import Tkinter 

MIN_AREA = 32

# performance stats

_area_counter = {}
_precalc_points = 0

Point = collections.namedtuple('Point', ['x', 'y'])

def get_statistics():
    global _area_counter
    global _cached_points
    return ( sum([ x * _area_counter[x] for x in _area_counter ]), _precalc_points )

class ColorMap():
    def __init__(self, number_colors):
        colorstops = ( (255, 0, 0), (255, 255, 0), (0, 255,0),
                       (0, 255, 255), (0, 0, 255), (255, 0, 255),
                       (255, 255, 255), (0, 0, 0) )
        self.number_colors = number_colors
        c = (0,0,0)
        last_color = "#{:02X}{:02X}{:02X}".format(c[0],c[1],c[2])
        self._colormap = [last_color] * number_colors
        self._c = len(colorstops)
        self._theta = int(float(number_colors / self._c))
        self._rho = 1.0 / self._theta;
                    
        prev= -1
        current=0

        index = 0
        for c in range(self._c):
            prev_color=colorstops[prev]
            current_color=colorstops[current]
            Lambda = 1.0
            for k in range(self._theta):            
                cmix = map(operator.add,
                map(operator.mul, prev_color, (Lambda,)*3),
                map(operator.mul, current_color, (1.0-Lambda,)*3))
                self._colormap[index] = "#{:02X}{:02X}{:02X}".format(int(cmix[0]),int(cmix[1]),int(cmix[2]))
                index += 1
                Lambda -= self._rho
            prev=current
            current+=1

    def key_map(self, key):
        if key < 0.0:
            key = 0
        if key > 1.0:
            key = 1.0
        key = 1.0 - key
        key = 1.0 - key * key
        
        k = int(key * self.number_colors + 0.5)
        if k >= self.number_colors:
            k = self.number_colors - 1
        return k
    
    def __getitem__(self, key):
        return self._colormap[self.key_map(key)]
        
    def __setitem__(self, key, value):
        self._colormap[self.key_map(key)] = value

# corner points
# generates points in the following order:
# 
# width = 1:
#  [1]
# 2:
#   @ [1]
#  [3][2]
# 3:
#   @    [1]
#        [2]
#  [5][4][3]

        
def corner_sweeper(top_left, bottom_right):
    xE, yE = bottom_right.x, top_left.y
    xS, yS = bottom_right.x - 1, bottom_right.y

    # yield east side, top to bottom
    
    x, y = xE, yE
    while y <= bottom_right.y:
        yield x, y, 'E'
        y += 1

    # yield south side, right to left

    x, y = xS, yS
    while True:
        if x >= top_left.x:
            yield x, y, 'S'
            x -= 1
        else:
            break

    yield bottom_right.x, bottom_right.y, 'SUCCESS'

def rectangle_sweeper(top_left, new_bottom_right):
    y = top_left.y
    while y <= new_bottom_right.y:
        x = top_left.x
        while x <= new_bottom_right.x:
            yield x, y
            x += 1
        y += 1
 
def mandelbrot_map(map_args):
    C, addr, plane, maxit, scale = map_args

    it = plane[addr]

    if it == 0: # not previously calculated point, most common scenario
        Cre = C.real
        Cim = C.imag
        Hre = 0
        Him = 0
        Zre = 0
        Zim = 0
        Zre2 = 0
        Zim2 = 0
        check = 3
        check_cnt = 0
        update = 10
        update_cnt = 0
        epsilon = scale / 2.0
        while it < maxit:
            Zim = 2 * Zre * Zim + Cim
            Zre = Zre2 - Zim2 + Cre
            Zre2 = Zre * Zre
            Zim2 = Zim * Zim
            if Zre2 + Zim2 < 4.0:
                if abs(Zre - Hre) < epsilon:
                    if abs(Zim - Him) < epsilon:
                        # period detected
                        it = maxit
                        break
                it += 1
                if check == check_cnt:
                    check_cnt = 0
                    if update == update_cnt:
                        update_cnt = 0
                        check *= 2
                    update_cnt += 1
                    
                    Hre = Zre
                    Him = Zim
                check_cnt += 1
            else:
                break
        plane[addr] = it
    else:
        global _precalc_points # previously calculated point, update stats
        _precalc_points += 1
        
    return it / maxit

def mandelbrot_recurse(top_left, bottom_right, params):
    plane, plane_width, shift, scale, center, maxit, paint, check = params

    width = bottom_right.x - top_left.x + 1
    height = bottom_right.y - top_left.y + 1

    eps = 0.5 / maxit
    
    map_args = [ 0, 0, plane, maxit, scale.real ]
    
    x = top_left.x
    y = top_left.y

    # determin horizontal and vertical break points
    
    xs = x - shift.x
    ys = y - shift.y
    map_args[0] = center + xs * scale.real + ys * 1j * scale.imag
    map_args[1] = x + plane_width * y
    corner_val = mandelbrot_map(map_args)

    # diagonal break point
    
    dz = 1
    d0 = scale.real + 1j * scale.imag
    d1 = 1 + plane_width
    xs = x + dz - shift.x
    ys = y + dz - shift.y
    map_args[0] = center + xs * scale.real + ys * 1j * scale.imag
    map_args[1] = x + dz + plane_width * (y + dz)
    while (dz < width) and (dz < height):
        if abs(mandelbrot_map(map_args) - corner_val) < eps:
            dz += 1
            map_args[0] += d0
            map_args[1] += d1
        else:
            break

    area_bottom_right = None

    dx = dz
    dy = dz

    if check():
        return

    while area_bottom_right == None and (dx * dy > MIN_AREA) and (dx > 1) and (dy > 1):
        for x, y, sc in corner_sweeper(top_left, Point(top_left.x + dx - 1, top_left.y + dy - 1)):
            map_args[0] = center + (x - shift.x) * scale.real + (y - shift.y) * 1j * scale.imag
            map_args[1] = x + plane_width * y
            it = mandelbrot_map(map_args)
            if sc == 'SUCCESS':
                area_bottom_right = Point(x, y)
            elif abs(mandelbrot_map(map_args) - corner_val) >= eps:
                if sc == 'E':
                    dx -= 1 # fail on east side, move east side west
                else:
                    dy -= 1 # fail on south side, move south side north
                break
            paint(Point(x, y), None, it)

    if area_bottom_right == None:
        break_point = Point((3 * top_left.x + bottom_right.x) // 4, (3 * top_left.y + bottom_right.y) // 4)
        
        width = break_point.x - top_left.x
        height = break_point.x - top_left.x

        if width > 5 and height > 5 and width * height > 50:
            status = mandelbrot_recurse(top_left, break_point, params)
            if status != None:
                return status
        else:
            cnt = 0
            for x, y in rectangle_sweeper(top_left, break_point):
                map_args[0] = center + (x - shift.x) * scale.real + (y - shift.y) * 1j * scale.imag
                map_args[1] = x + plane_width * y
                paint(Point(x, y), None, mandelbrot_map(map_args))
    else:
        area = (area_bottom_right.x + 1 - top_left.x) * (area_bottom_right.y + 1 - top_left.y)
        _area_counter[area] = _area_counter.get(area, 0) + 1
        paint(top_left, area_bottom_right, corner_val)
        break_point = Point(top_left.x + dx - 1, top_left.y + dy - 1)

    # [ top_left <= point <= break_point ] taken care of        
    # recurse over rectangles to the east, southeast and south

    if check():
        return

    rects = (
    ((break_point.x + 1, top_left.y),        (bottom_right.x, break_point.y)),
    ((break_point.x + 1, break_point.y + 1), (bottom_right.x, bottom_right.y)),
    ((top_left.x,        break_point.y + 1), (break_point.x,  bottom_right.y)))
    
    for tl, br in rects:
        if check():
            return
        recurse_top_left     = Point(tl[0], tl[1])
        recurse_bottom_right = Point(br[0], br[1])
        
        width = recurse_bottom_right.x - recurse_top_left.x + 1
        height = recurse_bottom_right.y - recurse_top_left.y + 1

        if (width < 1) or (height < 1):
            continue

        if (width > 5) and (height > 5) and (width * height > 50):
            mandelbrot_recurse(recurse_top_left, recurse_bottom_right, params)
        else: # only a small strip to paint, don't recurse
            for x, y in rectangle_sweeper(recurse_top_left, recurse_bottom_right):
                map_args[0] = center + (x - shift.x) * scale.real + (y - shift.y) * 1j * scale.imag
                map_args[1] = x + plane_width * y
                paint(Point(x, y), None, mandelbrot_map(map_args))

class MandelApp(Tkinter.Frame):
    START_WIDTH = 512
    START_HEIGHT = 512

    def __init__(self, master=None):
        self.quit = False        
        self.width = MandelApp.START_WIDTH
        self.height = MandelApp.START_HEIGHT

        self.tkroot = Tkinter.Tk()
        Tkinter.Frame.__init__(self, master)
        self.pack()
        self.canvas = Tkinter.Canvas(master=self, width=self.width, height=self.height, takefocus=True)
        #self.canvas.bind('<Key-Return>', self.mandel_func)
        self.canvas.bind("<ButtonRelease-1>", self.handle_zoom)
        self.canvas.bind("<ButtonRelease-3>", self.handle_quit)
        #self.canvas.bind("<ButtonRelease-3>", self.handle_right_mouse)
        self.canvas.pack()
        self.paint_cnt = 0

    def handle_left_mouse(self, event):
        print("Jahadu!")

    @staticmethod
    def zero_yielder(n=0):
        count = 0
        while count < n:
            count += 1
            yield 0

    def paint(self, top_left, bottom_right, c, color=None):
        if color is None:
            color = self.colormap[c]
        if bottom_right is None:
            x, y = top_left
            self.canvas.create_rectangle(x, y, x+1, y+1, fill=color, outline="")
        else:
            self.canvas.create_rectangle(
            top_left.x, top_left.y, bottom_right.x+1, bottom_right.y+1, fill=color, outline="")
        self.paint_cnt += 1
        if self.paint_cnt == 2000:
            self.paint_cnt = 0
            self.update(0.0)

    def handle_quit(self, event):
        print("** quit")
        self.quit = True

    def handle_zoom(self, event):
        print("** zoom")
        self.zoom = True
        self.zoomx = event.x
        self.zoomy = event.y

    def update(self, t=0.001):
        if t > 0.00001:
            time.sleep(t)
        self.canvas.update()

    def check(self):
        return self.quit or self.zoom
   
    def xyzzy(self):
        center = -1.0 + 0j
        zoom = 2
        maxit = 400
        self.colormap = ColorMap(maxit)

        status = None
        self.zoom = False
        self.draw = True

        plane = None

        while not self.quit:
            shift = Point(self.width / 2, self.height / 2)
            scale = zoom * (1.0 / self.width + 1j / self.height)
            top_left = Point(0, 0)
            bottom_right = Point(self.width - 1, y = self.height - 1)
            if self.draw:
                cnt = 0
                if plane is not None:
                    for x, y in rectangle_sweeper(top_left, bottom_right):
                        c = plane[cnt] / (12.0 * maxit)
                        if c == 0:
                            c = 1.0
                        else:
                            c = 1.0 - c
                        if (x ^ y) & 1:
                            c = 0.5 * c
                        self.paint(Point(x, y), None, c)
                        cnt += 1
                plane = array.array('d', self.zero_yielder(self.width*self.height))     
                params = (plane, self.width, shift, scale, center, maxit, self.paint, self.check)
                status = mandelbrot_recurse(top_left, bottom_right, params)
                self.draw = False
            else:
                self.update(0.1)
            if self.zoom:
                center += (self.zoomx - shift.x) * scale.real + (self.zoomy - shift.y) * 1j * scale.imag
                zoom *= 0.125
                scale = 2 * zoom * (1.0 / self.width + 1j / self.height)
                self.draw = True
                params = (plane, self.width, shift, scale, center, maxit, self.paint, self.check)
                self.zoom = False
                print("zooming: {0} {1}".format(center, zoom))
            elif self.quit:
                print("quitting")
            
if __name__ == "__main__":
#    for x, y in rectangle_sweeper(Point(0,0), Point(4,5)):
#        print(x, y)
#    quit()

    app = MandelApp()
    app.xyzzy()
    print(get_statistics())
    print(_area_counter)
