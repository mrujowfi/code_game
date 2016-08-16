#coding=utf-8
#https://documen.tician.de/pycuda/

import pycuda.autoinit
import pycuda.driver as drv
import numpy
from pycuda.compiler import SourceModule
import datetime
a = numpy.random.randn(400).astype(numpy.float32)
b = numpy.random.randn(400).astype(numpy.float32)
start = datetime.datetime.now()
'''
mod = SourceModule(u"""
    __global__ void multiply_them(float *dest, float *a, float *b)
    {
        const int i = threadIdx.x;
        int j = 0;
        dest[i] = a[i] * b[i] + b[i];
        for(j=0; j<10000; j++){
            dest[i] = a[i] * dest[i] + b[i];
        }
    }
    """)
multiply_them = mod.get_function("multiply_them")
dest = numpy.zeros_like(a)



multiply_them( drv.Out(dest), drv.In(a), drv.In(b), block=(400,1,1), grid=(1,1,1))
# print help(multiply_them)
print len(dest)
# print a
# print b
# print dest
# print dest-a*b

'''


def multiply_them(dest2, a, b):
    for i in range(len(a)):
        j = 0
        each = a[i] * b[i] + b[i]
        while j<10000:
            each = a[i] * each + b[i]
            j += 1
        dest2.append(each)

if __name__ == '__main__':
    dest2 = []
    multiply_them(dest2, a, b)
    print len(dest2)

end = datetime.datetime.now()
print (end-start)