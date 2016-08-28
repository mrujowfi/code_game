#coding=utf-8
import sys
import timing
import time
from selenium import webdriver
import traceback
import datetime
import multiprocessing
import copy
import ctypes
import random

g_version = 'v3.0.0'
'''
气眼检测 v1.0
波纹探测墙 v1.1
波纹探测岛 v2.0
探索顺序3,2,4,1 v2.1
初级残影检测 v2.2
改成进程类实现单机多进程 v2.3
效果拔群... v2.3.2
进程共享残影图 v2.4.1
可视进度 v2.4.2
加入坐标权重, 废除初级残影检测 v3.0.0
'''

global driver


class Point(ctypes.Structure):
    _fields_ = [('line', ctypes.c_int32), ('row', ctypes.c_int32), ('count', ctypes.c_int32)]  # count for wall


class ProcRobot(multiprocessing.Process):
    def __init__(self, args):
        multiprocessing.Process.__init__(self)
        self.globalArgs = dict()
        self.arg = args['arg']
        self.level = 0
        self.line = 0
        self.row = 0
        self.pos = 0
        self.house = 0
        self.house_list = 0
        self.history = 0
        self.num_map = 0
        # each shadow position is 0b****1111, means can start walking (up, down, left, right)
        self.shadow = args['shadow']
        self.sum_second = 0
        self.sum_walk = args['sum_walk']
        self.mission_type = int(args['mission_type'])
        self.reverse = int(args['reverse'])
        self.result = args['result']
        self.data_lock = args['data_lock']
        self.start_time = ''
        self.end_time = ''
        if self.reverse == 0:
            self.queue = args['queue']
        elif self.reverse == 1:
            self.queue = args['queue_reverse']
        self.start_pos = args['start_pos'][self.reverse]
        self.score = 0
        self.count_wall = args['count_wall']
        self.syn = args['syn']
        self.q_wc = args['q_wc']  # wait count
        self.q_hc = args['q_hc']  # have counted
        self.n_wp = args['n_wp']  # length of q_wp
        self.q_wp = args['q_wp']  # wait for picking
        self.n_hp = args['n_hp']  # length of q_hp
        self.q_hp = args['q_hp']  # have picked
        self.walk_list = None  # check if a pos is valid
        self.rule = args['rule']
        self.proc_num = args['proc_num']
        self.wait_num = args['wait_num']
        self.test_num = 0
        self.percent = args['percent']
        self.total_queue = 0

    def run(self):
        print str(self.pid)+' ('+str(self.mission_type)+', '+str(self.reverse)+') '+self.name+' start '
        try:
            self.init(self.arg)
            while True:
                value = self.get_value()
                ans = self.proc_q_wc()
                if ans is not None:
                    self.data_lock.acquire()
                    self.result.put(ans)
                    self.syn.value = 4
                    self.data_lock.release()
                    self.end_time = datetime.datetime.now()
                    print 'lv:%s, (%d, %d) %s, %d procs, %d/%d wa_lks, p:%.2f, avg: %.2f seconds,  %s' % (
                        self.level, self.mission_type, self.reverse, g_version, self.proc_num,
                        self.sum_walk.value, self.total_queue, self.percent,
                        (self.end_time-self.start_time).seconds/float(self.sum_walk.value),
                        (self.end_time-self.start_time)
                    )
                    self.print_array(self.q_hc)
                if self.syn.value == 4:
                    break
        except Exception, e:
            print 'error', e
            time.sleep(1)
            print traceback.format_exc()
        with self.wait_num.get_lock():
            self.wait_num.value += 1
        print str(self.pid)+' ('+str(self.mission_type)+', '+str(self.reverse)+') '+self.name+' stop '

    def init(self, question):
        self.arg = question.replace('\n', '')
        self.level = int(self.arg.split('&')[0].split('=')[1])
        self.line = int(self.arg.split('&')[1].split('=')[1])
        self.row = int(self.arg.split('&')[2].split('=')[1])
        self.pos = self.arg.split('&')[3].split('=')[1]
        self.house = [[0 for i in range(self.row)] for j in range(self.line)]
        self.house_list = []
        self.history = ''
        sys.setrecursionlimit(1000*self.line*self.row)
        self.num_map = {'num_-1': 0, 'num_0': 0, 'num_1': 0, 'num_2': 0, 'num_3': 0, 'num_4': 0}
        self.sum_second = 0

        # init each position
        for each in range(len(self.pos)):
            j = each%self.row
            i = (each-j)/self.row
            if self.pos[each] == '1':
                self.house[i][j] = -1
                self.num_map['num_-1'] += 1
            else:
                self.house[i][j] = 0

        # count position value
        for i in range(self.line):
            for j in range(self.row):
                if self.house[i][j] >= 0:
                    self.pos_count(self.house, i, j, self.num_map, True)

        i_range = range(self.line)
        j_range = range(self.row)
        queue_list = [(i, j) for i in i_range for j in j_range]
        if self.reverse == 1:
            queue_list.reverse()
        self.walk_list = list()
        for each in queue_list:
            i, j = each
            if self.house[i][j] != -1:
                self.walk_list.append(each)

        self.total_queue = len(self.walk_list)
        # 5% percent of not any test points nearby(9*9) the result point
        self.test_num = ProcRobot.make_test(self.line, self.row, self.percent)

        if self.mission_type != 0 or self.reverse != 0:
            time.sleep(1)  # stop ohter proc, while (0, 0) init shared data
        self.data_lock.acquire()
        if self.queue.qsize() == 0:
            random.shuffle(self.walk_list)
            for k in range(len(self.walk_list)):
                self.queue.put(self.walk_list[k])  # a queue for random points

        self.start_time = datetime.datetime.now()
        if self.mission_type == 0 and self.reverse == 0:
            for i in range(self.test_num):
                if self.queue.qsize > 0:
                    self.q_wc.put(self.queue.get())  # init first test points for summary calc
                else:
                    break
            print 'lv:%s start time: %s' % (self.level, self.start_time.strftime("%Y%m%d-%H%M%S.%f"))
            print self.arg
            print 'line: %d\trow: %d' % (self.line, self.row)
            print 'test_num: %d/%d, %f' % (self.test_num, self.total_queue, self.percent)
            ProcRobot.print_house(self.house)
            self.syn.value = 1
        self.data_lock.release()

    @staticmethod
    def print_house(temp_house):
        print ' '*2+'\t',
        for j in range(len(temp_house[0])):
            print '%2d\t' % j,
        print ' '
        for i in range(len(temp_house)):
            each = temp_house[i]
            print '%2d\t' % i,
            for each2 in each:
                print '%2d\t' % each2,
            print ' '

    def print_array(self, temp_array):
        print ' '*5+'\t',
        for j in range(self.row):
            print '%5d\t' % j,
        print ' '
        for i in range(self.line):
            print '%5d\t' % i,
            for k in range(self.row):
                print '%5d\t' % (temp_array[self.row*i + k]),
            print ' '

    def get_value(self):
        result = self.syn.value
        if result == 0:
            with self.wait_num.get_lock():
                self.wait_num.value += 1
            while True:
                time.sleep(5)
                result = self.syn.value
                if result != 0:
                    with self.wait_num.get_lock():
                        self.wait_num.value -= 1
                        # print '(%d, %d)\t\t lbg_wait %d -> %d' % (self.mission_type, self.reverse, self.wait_num.value+1, self.wait_num.value)
                    break
        return result

    @staticmethod
    def make_test(x, y, p):
        result = 1
        mult = (1 - 81.0/(x*y))*(1 - 81.0/(x*y - 1))
        while mult > p:
            result += 1
            mult *= (1 - 81.0/(x*y - result))
        return result

    # count one position value
    def pos_count(self, temp_house, i, j, temp_num_map, firstInit=False):

        n = 0
        if i-1 >= 0 and temp_house[i-1][j] >= 0:
            n += 1
        if i+1 < self.line and temp_house[i+1][j] >= 0:
            n += 1
        if j-1 >= 0 and temp_house[i][j-1] >= 0:
            n += 1
        if j+1 < self.row and temp_house[i][j+1] >= 0:
            n += 1
        if not firstInit:
            temp_num_map['num_'+str(temp_house[i][j])] -= 1
        temp_num_map['num_'+str(n)] += 1
        temp_house[i][j] = n

    def multi_area(self, temp_house, block_line, block_row):

        #wave all blocks, and check if A-B==0 or A-B==2
        #wide is highest when travelling
        block_now = copy.deepcopy(temp_house)
        selected_list = []
        selected_list.append((block_line, block_row, 1))#(self.line, self.row, depth)
        search_wall = {'state': 0, 'cross': 0}

        #select all linked blocks
        #print 'block', block_line, block_row
        #print_house(block_now)
        try:
            block_now[block_line][block_row] = -2
            if block_line == 0 or block_line == self.line-1 or block_row == 0 or block_row == self.row-1:
                search_wall['wall-2'] = 1
            result = self.travel_block(block_now, selected_list, search_wall)
        except RuntimeError, e:
            print 'error', e
            result = False

        #analyse wall to wall
        if not result:
            result = self.analyze_multi(block_now)
            if result:
                #print 'analyse block true'
                #print_house(block_now)
                pass
        else:
            #print 'travel block true'
            #print_house(block_now)
            pass


        #print result
        #print_house(block_now)

        return result

    def travel_block(self, block_now, selected_list, search_wall):

        if len(selected_list) == 0:
            return False
        i, j, depth = selected_list.pop(0)

        #print_house(block_now)

        #select all blocks nearby
        peer_block = 0
        if i > 0:
            if block_now[i-1][j] == -1:
                #up
                block_now[i-1][j] = -1 - (depth+1)
                selected_list.append((i-1, j, depth+1))
            #elif block_now[i-1][j] == block_now[i][j]:
            #    peer_block += 1
        if i+1 < self.line:
            if block_now[i+1][j] == -1:
                #down
                block_now[i+1][j] = -1 - (depth+1)
                selected_list.append((i+1, j, depth+1))
            #elif block_now[i+1][j] == block_now[i][j]:
            #    peer_block += 1
        if j > 0:
            if block_now[i][j-1] == -1:
                #left
                block_now[i][j-1] = -1 - (depth+1)
                selected_list.append((i, j-1, depth+1))
            #elif block_now[i][j-1] == block_now[i][j]:
            #    peer_block += 1
        if j+1 < self.row:
            if block_now[i][j+1] == -1:
                #right
                block_now[i][j+1] = -1 - (depth+1)
                selected_list.append((i, j+1, depth+1))
            #elif block_now[i][j+1] == block_now[i][j]:
            #    peer_block += 1

        if peer_block > 2:
            search_wall['cross'+str(-1 - (depth))] = 1
        if search_wall.__contains__('cross'+str(-1 - (depth-1))):
            search_wall['cross'] += 1
            if search_wall['cross'] > 1:
                return True
            elif search_wall['cross'] == 1 and search_wall['state'] > 0:
                return True

        if i > 0 and j > 0 and block_now[i-1][j-1] == -1:
            #up,left
            block_now[i-1][j-1] = -1 - (depth+1)
            selected_list.append((i-1, j-1, depth+1))
        if i+1 < self.line and j > 0 and block_now[i+1][j-1] == -1:
            #down,left
            block_now[i+1][j-1] = -1 - (depth+1)
            selected_list.append((i+1, j-1, depth+1))
        if i > 0 and j+1 < self.row and block_now[i-1][j+1] == -1:
            #up,right
            block_now[i-1][j+1] = -1 - (depth+1)
            selected_list.append((i-1, j+1, depth+1))
        if i+1 < self.line and j+1 < self.row and block_now[i+1][j+1] == -1:
            #down,right
            block_now[i+1][j+1] = -1 - (depth+1)
            selected_list.append((i+1, j+1, depth+1))

        #mark this wave if wall
        if i == 0 or i == self.line-1 or j == 0 or j == self.row-1:
            search_wall['wall'+str(-1 - (depth))] = 1
            #print 'walled', (-1 - (depth))

        if search_wall['state'] == 0:
            #searching wall1
            if search_wall.__contains__('wall'+str(-1 - (depth-1))):
                if search_wall['cross'] > 1:
                    return True
                #print (-1 - (depth)), '0->1'
                search_wall['state'] = 1
        elif search_wall['state'] == 1:
            #in wall1
            if search_wall['cross'] > 1:
                return True
            if search_wall.__contains__('wall'+str(-1 - (depth-1))):
                pass
            else:
                #print (-1 - (depth)), '1->2'
                search_wall['state'] = 2
        elif search_wall['state'] == 2:
            #searching wall2
            if search_wall['cross'] > 1:
                return True
            if search_wall.__contains__('wall'+str(-1 - (depth-1))):
                #print (-1 - (depth)), '2->Ture'
                return True

        if len(selected_list) == 0:
            if search_wall['state'] == 2:
                #searching wall2
                if search_wall.__contains__('wall'+str(-1 - (depth))):
                    #print (-1 - depth), '2->Ture'
                    return True

        return self.travel_block(block_now, selected_list, search_wall)

    # travel 4 walls to analyze
    def analyze_multi(self, block_now):

        target = 0
        searching = True
        if block_now[0][0] < -1:
            #selected
            for j in range(self.row):
                if searching:
                    if block_now[0][j] >= -1:
                        target += 1
                        if target == 2:
                            return True
                        searching = False
                else:
                    if block_now[0][j] < -1:
                        searching = True
            for i in range(self.line):
                if searching:
                    if block_now[i][self.row-1] >= -1:
                        target += 1
                        if target == 2:
                            return True
                        searching = False
                else:
                    if block_now[i][self.row-1] < -1:
                        searching = True
            for j in range(self.row-1, -1, -1):
                if searching:
                    if block_now[self.line-1][j] >= -1:
                        target += 1
                        if target == 2:
                            return True
                        searching = False
                else:
                    if block_now[self.line-1][j] < -1:
                        searching = True
            for i in range(self.line-1, -1, -1):
                if searching:
                    if block_now[i][0] >= -1:
                        target += 1
                        if target == 2:
                            return True
                        searching = False
                else:
                    if block_now[i][0] < -1:
                        searching = True
        else:
            #not selected
            for j in range(self.row):
                if searching:
                    if block_now[0][j] < -1:
                        target += 1
                        if target == 2:
                            return True
                        searching = False
                else:
                    if block_now[0][j] >= -1:
                        searching = True
            for i in range(self.line):
                if searching:
                    if block_now[i][self.row-1] < -1:
                        target += 1
                        if target == 2:
                            return True
                        searching = False
                else:
                    if block_now[i][self.row-1] >= -1:
                        searching = True
            for j in range(self.row-1, -1, -1):
                if searching:
                    if block_now[self.line-1][j] < -1:
                        target += 1
                        if target == 2:
                            return True
                        searching = False
                else:
                    if block_now[self.line-1][j] >= -1:
                        searching = True
            for i in range(self.line-1, -1, -1):
                if searching:
                    if block_now[i][0] < -1:
                        target += 1
                        if target == 2:
                            return True
                        searching = False
                else:
                    if block_now[i][0] >= -1:
                        searching = True

        return False

    def are_you_ok(self, temp_house, block_line, block_row, temp_num_map, depth):

        num_1, num0, num1, num2, num3, num4 = (temp_num_map['num_-1'], temp_num_map['num_0'], temp_num_map['num_1'], temp_num_map['num_2'], temp_num_map['num_3'], temp_num_map['num_4'])
        #print num_1, num0, num1, num2, num3, num4

        if self.score < num_1:
            self.score = num_1

        #sure
        if num0 == 1 and num1 == 0 and num2 == 0 and num3 == 0 and num4 == 0:
            return True
        if num0 > 0:
            return False
        if num1 > 2:
            return False
        if num0 == 0 and num3 == 0 and num4 == 0:
            return None
        #if num_1*4>self.line*self.row and num_1*2<self.line*self.row and block_line!=None and block_row!=None and multi_area(temp_house, block_line, block_row):
        #    return False
        if depth % 16 == 0:
            if self.multi_area(temp_house, block_line, block_row):
                return False
            if self.syn.value == 4:
                # print self.name + ' other'
                return False

        #possibly
        return None

    def robot_start(self):

        #origin_house at self.house_list[0]

        #print travel(2, 2, 1)
        '''
        self.house_list.append((copy.deepcopy(self.house), copy.deepcopy(self.num_map)))
        self.history = ''
        i = 30
        j = 6
        result = travel_first(i, j, 1)
        if result[0]:
            url = 'http://www.qlcoder.com/train/crcheck?x='+str(i+1)+'&y='+str(j+1)+'&path='+self.history
            print url
        '''
        # print 'search '+str(mission_type)+' '+str(reverse)
        timing.start()
        self.house_list.append((copy.deepcopy(self.house), copy.deepcopy(self.num_map)))

        while True:
            i, j = (-1, -1)
            self.data_lock.acquire()
            result_size = self.result.qsize()
            queue_size = self.queue.qsize()
            if queue_size > 0:
                i, j = self.queue.get()
                self.data_lock.release()
            else:
                self.data_lock.release()
                print self.name+' break1'
                break

            if i != -1 and j != -1:  # and result_size == 0:
                with self.sum_walk.get_lock():
                    self.sum_walk.value += 1
                # print '%d,%d\r' % (i, j),
                print '(%d, %d)\twalk\t%d, %d\t%s%d/%d' \
                      % (self.mission_type, self.reverse, i, j,
                         '+' if self.reverse == 0 else '-', self.total_queue-queue_size, self.total_queue)
                self.history = ''
                self.score = 0
                self.count_wall[self.row*i + j] = self.score
                result = self.travel(i, j, 1)
                self.count_wall[self.row*i + j] = self.score
                if result[0]:
                    url = 'http://www.qlcoder.com/train/crcheck?x='+str(i+1)+'&y='+str(j+1)+'&path='+self.history
                    print url
                    return url
            else:
                print self.name+' break2'
                break

        # if self.mission_type == 0 and self.reverse == 0:
        #     self.print_array(self.count_wall)

        return None

    def proc_q_wc(self):

        self.house_list.append((copy.deepcopy(self.house), copy.deepcopy(self.num_map)))

        while True:
            i, j = (-1, -1)
            self.data_lock.acquire()
            result_size = self.result.qsize()
            q_wc_size = self.q_wc.qsize()
            if q_wc_size > 0:
                i, j = self.q_wc.get()
                self.data_lock.release()
            else:
                self.data_lock.release()
                if self.n_wp.value == self.test_num:
                    # syn 1 -> 2, all other proc is done
                    test_list = list()
                    for i in range(self.n_wp.value):
                        test_list.append(self.q_wp[i].count)
                    test_list.sort()

                    # print 'rule: %d %d %d %d %d' % (self.n_wp.value, len(test_list), int(0.29*self.test_num), int(0.89*self.test_num), int(0.99*self.test_num))
                    self.rule[0] = test_list[int(0.29*self.test_num)]
                    self.rule[1] = test_list[int(0.89*self.test_num)]
                    self.rule[2] = test_list[int(0.99*self.test_num)]
                    print 'rule: %d %d %d' % (self.rule[0], self.rule[1], self.rule[2])
                self.pick_seek()
                return None

            if i != -1 and j != -1 and result_size == 0:
                with self.sum_walk.get_lock():
                    self.sum_walk.value += 1
                # print '%d,%d\r' % (i, j),
                print '(%d, %d)\twalk\t%d, %d\t%d/%d' \
                      % (self.mission_type, self.reverse, i, j, self.sum_walk.value, self.total_queue)
                self.history = ''
                self.score = 0
                self.count_wall[self.row*i + j] = self.score
                result = self.travel(i, j, 1)
                self.count_wall[self.row*i + j] = self.score
                # print self.score
                self.data_lock.acquire()
                self.q_hc[self.row*i + j] = self.score
                self.q_wp[self.n_wp.value] = (i, j, self.score)
                self.n_wp.value += 1
                self.data_lock.release()
                if result[0]:
                    url = 'http://www.qlcoder.com/train/crcheck?x='+str(i+1)+'&y='+str(j+1)+'&path='+self.history
                    print url
                    # self.sum_second += timing.stop(bPrint=False)
                    return url
            else:
                print self.name+' break2'
                break
        return None

    def pick_seek(self):
        # pick a point from q_wp
        result = 0
        if self.rule[0] == -1:
            # no rule
            i, j = self.queue.get()
            while self.q_hc[self.row*i + j] > 0:
                i, j = self.queue.get()
            self.q_wc.put((i, j))
            print '(%d, %d) pick %d, %d random no rule' % (self.mission_type, self.reverse, i, j)
            return
        wp_list = dict()
        for i in range(self.n_wp.value):
            each = self.q_wp[i]
            if each.count != -1:
                wp_list[str(each.count)] = (each.line, each.row, i)
        wp_keys = wp_list.keys()
        int_wp_keys = [int(i) for i in wp_keys]
        int_wp_keys.sort()

        # seek from the point
        if int(int_wp_keys[-1]) < self.rule[0]:
            # < 30%
            i, j = self.queue.get()
            while self.q_hc[self.row*i + j] > 0:
                i, j = self.queue.get()
            self.q_wc.put((i, j))
            print '(%d, %d) pick %d, %d random' % (self.mission_type, self.reverse, i, j)
            return

        result = wp_list[str(int_wp_keys[-1])]

        # del the point in q_wp
        self.q_wp[result[2]].count = -1

        # insert into q_hp
        line = result[0]
        row = result[1]
        self.q_hp[self.n_hp.value] = (line, row, -1)
        with self.n_hp.get_lock():
            self.n_hp.value += 1

        if int(int_wp_keys[-1]) < self.rule[1]:
            print '(%d, %d) pick %d, %d %d horse' % (self.mission_type, self.reverse, result[0], result[1], int_wp_keys[-1])
            # 30 ~ 90, horse
            i, j = line-2, row-1
            if self.test_point(i, j) is True and self.house[i][j] != -1 and self.q_hc[self.row*i + j] == -1:
                self.q_wc.put((i, j))
            i, j = line-2, row+1
            if self.test_point(i, j) is True and self.house[i][j] != -1 and self.q_hc[self.row*i + j] == -1:
                self.q_wc.put((i, j))
            i, j = line+2, row-1
            if self.test_point(i, j) is True and self.house[i][j] != -1 and self.q_hc[self.row*i + j] == -1:
                self.q_wc.put((i, j))
            i, j = line+2, row+1
            if self.test_point(i, j) is True and self.house[i][j] != -1 and self.q_hc[self.row*i + j] == -1:
                self.q_wc.put((i, j))
            i, j = line-1, row-2
            if self.test_point(i, j) is True and self.house[i][j] != -1 and self.q_hc[self.row*i + j] == -1:
                self.q_wc.put((i, j))
            i, j = line+1, row-2
            if self.test_point(i, j) is True and self.house[i][j] != -1 and self.q_hc[self.row*i + j] == -1:
                self.q_wc.put((i, j))
            i, j = line-1, row+2
            if self.test_point(i, j) is True and self.house[i][j] != -1 and self.q_hc[self.row*i + j] == -1:
                self.q_wc.put((i, j))
            i, j = line+1, row+2
            if self.test_point(i, j) is True and self.house[i][j] != -1 and self.q_hc[self.row*i + j] == -1:
                self.q_wc.put((i, j))
        elif int(int_wp_keys[-1]) < self.rule[2]:
            print '(%d, %d) pick %d, %d %d horse+cross' % (self.mission_type, self.reverse, result[0], result[1], int_wp_keys[-1])
            # 90 ~ 99, horse+cross
            i, j = line-2, row-1
            if self.test_point(i, j) is True and self.house[i][j] != -1 and self.q_hc[self.row*i + j] == -1:
                self.q_wc.put((i, j))
            i, j = line-2, row+1
            if self.test_point(i, j) is True and self.house[i][j] != -1 and self.q_hc[self.row*i + j] == -1:
                self.q_wc.put((i, j))
            i, j = line+2, row-1
            if self.test_point(i, j) is True and self.house[i][j] != -1 and self.q_hc[self.row*i + j] == -1:
                self.q_wc.put((i, j))
            i, j = line+2, row+1
            if self.test_point(i, j) is True and self.house[i][j] != -1 and self.q_hc[self.row*i + j] == -1:
                self.q_wc.put((i, j))
            i, j = line-1, row-2
            if self.test_point(i, j) is True and self.house[i][j] != -1 and self.q_hc[self.row*i + j] == -1:
                self.q_wc.put((i, j))
            i, j = line+1, row-2
            if self.test_point(i, j) is True and self.house[i][j] != -1 and self.q_hc[self.row*i + j] == -1:
                self.q_wc.put((i, j))
            i, j = line-1, row+2
            if self.test_point(i, j) is True and self.house[i][j] != -1 and self.q_hc[self.row*i + j] == -1:
                self.q_wc.put((i, j))
            i, j = line+1, row+2
            if self.test_point(i, j) is True and self.house[i][j] != -1 and self.q_hc[self.row*i + j] == -1:
                self.q_wc.put((i, j))
            # cross
            i, j = line-1, row
            if self.test_point(i, j) is True and self.house[i][j] != -1 and self.q_hc[self.row*i + j] == -1:
                self.q_wc.put((i, j))
            i, j = line+1, row
            if self.test_point(i, j) is True and self.house[i][j] != -1 and self.q_hc[self.row*i + j] == -1:
                self.q_wc.put((i, j))
            i, j = line, row-1
            if self.test_point(i, j) is True and self.house[i][j] != -1 and self.q_hc[self.row*i + j] == -1:
                self.q_wc.put((i, j))
            i, j = line, row+1
            if self.test_point(i, j) is True and self.house[i][j] != -1 and self.q_hc[self.row*i + j] == -1:
                self.q_wc.put((i, j))
        else:
            print '(%d, %d) pick %d, %d %d square' % (self.mission_type, self.reverse, result[0], result[1], int_wp_keys[-1])
            # > 99, big square
            for m in range(-2, 3):
                for n in range(-2, 3):
                    i, j = line+m, row+n
                    if self.test_point(i, j) is True and self.house[i][j] != -1 and self.q_hc[self.row*i + j] == -1:
                        self.q_wc.put((i, j))
        return

    def test_point(self, line, row, wall_distance=0):
        if line - wall_distance < 0 or line + wall_distance >= self.line:
            return False
        elif row - wall_distance < 0 or row + wall_distance >= self.row:
            return False
        else:
            return True

    # move from (pos_line, pos_row)
    # return (result, (ul, ur, dl, dr))
    def travel_first(self, pos_line, pos_row, depth):

        result = (False, ((0, 0), (0, 0)))
        a_house, a_num_map = self.house_list[depth-1]
        house_now = copy.deepcopy(a_house)
        num_map_now = copy.deepcopy(a_num_map)
        this_shadow_line = [0, 0, 0, 0]#for up, down, left, right count


        #print pos_line, pos_row
        #print_house(house_now)
        #move up
        #if self.shadow[pos_line][pos_row][0] == 0:
        #    print 'shadow (%d, %d) %d' % (pos_line, pos_row, 0)
        if self.shadow[self.row*pos_line + pos_row] & 8 != 0 and pos_line-1 >= 0 and house_now[pos_line-1][pos_row] >= 0:
            no_shadow = False#flag for not use shadow because eye analyse
            house_up = copy.deepcopy(house_now)
            num_map_up = copy.deepcopy(num_map_now)
            inc = 1
            while pos_line-inc >= 0 and house_up[pos_line-inc][pos_row] >= 0:
                num_map_up['num_'+str(house_up[pos_line-(inc-1)][pos_row])] -= 1
                num_map_up['num_'+str(-1)] += 1
                house_up[pos_line-(inc-1)][pos_row] = -1
                this_shadow_line[0] += 1
                inc+=1
            #recount value
            for i in range(pos_line-inc if pos_line-inc>=0 else 0, (pos_line+2) if pos_line+1<self.line else self.line):
                for j in [pos_row-1, pos_row, pos_row+1] if pos_row-1>=0 and pos_row+1<self.row else [pos_row-1, pos_row] if pos_row-1>0 else [pos_row, pos_row+1] if pos_row+1<self.row else [pos_row,]:
                    if house_up[i][j] >= 0:
                        self.pos_count(house_up, i, j, num_map_up)
                        if house_up[i][j] == 0 or house_up[i][j] == 1:
                            no_shadow = True
            self.history = self.history[:depth-1]+'u'
            if depth % 100 == 0:
                #print self.history
                pass
            #print_house(house_up)
            self.house_list = self.house_list[:depth]+[(house_up,num_map_up),]
            result = self.travel(pos_line-(inc-1), pos_row, depth+1)
            shadow_line_excluded = self.excludeShadowUp(((pos_line-this_shadow_line[0], pos_row), (pos_line, pos_row)), result[1])
            #print result[1], shadow_line_excluded
            if no_shadow is False and shadow_line_excluded is not None:
                with self.shadow.get_lock():
                    for step in range(shadow_line_excluded[0][0], shadow_line_excluded[1][0]+1):
                        self.shadow[self.row*step + pos_row] &= 7
            if result[0]:
                return result

        #move down
        #if self.shadow[pos_line][pos_row][1] == 0:
        #    print 'shadow (%d, %d) %d' % (pos_line, pos_row, 1)
        if self.shadow[self.row*pos_line + pos_row] & 4 != 0 and pos_line+1 < self.line and house_now[pos_line+1][pos_row] >= 0:
            no_shadow = False#flag for not use shadow because eye analyse
            house_down = copy.deepcopy(house_now)
            num_map_down = copy.deepcopy(num_map_now)
            inc = 1
            while pos_line+inc < self.line and house_down[pos_line+inc][pos_row] >= 0:
                num_map_down['num_'+str(house_down[pos_line+(inc-1)][pos_row])] -= 1
                num_map_down['num_'+str(-1)] += 1
                house_down[pos_line+(inc-1)][pos_row] = -1
                this_shadow_line[1] += 1
                inc+=1
            #recount value
            for i in range(pos_line-1 if pos_line-1>=0 else 0, (pos_line+inc) if pos_line+inc<self.line else self.line):
                for j in [pos_row-1, pos_row, pos_row+1] if pos_row-1>=0 and pos_row+1<self.row else [pos_row-1, pos_row] if pos_row-1>0 else [pos_row, pos_row+1] if pos_row+1<self.row else [pos_row,]:
                    if house_down[i][j] >= 0:
                        self.pos_count(house_down, i, j, num_map_down)
                        if house_down[i][j] == 0 or house_down[i][j] == 1:
                            no_shadow = True
            self.history = self.history[:depth-1]+'d'
            if depth % 100 == 0:
                #print self.history
                pass
            #print_house(house_down)
            self.house_list = self.house_list[:depth]+[(house_down,num_map_down),]
            result = self.travel(pos_line+(inc-1), pos_row, depth+1)
            shadow_line_excluded = self.excludeShadowDown(((pos_line, pos_row), (pos_line+this_shadow_line[1], pos_row)), result[1])
            #print result[1], shadow_line_excluded
            if no_shadow is False and shadow_line_excluded is not None:
                with self.shadow.get_lock():
                    for step in range(shadow_line_excluded[0][0], shadow_line_excluded[1][0]+1):
                        #if step == '31' and pos_row == 6:
                        #print 'close', pos_line, pos_row, step, pos_row, this_shadow_line, shadow_line_excluded
                        self.shadow[self.row*step + pos_row] &= 11
            if result[0]:
                return result

        #move left
        #if self.shadow[pos_line][pos_row][2] == 0:
        #    print 'shadow (%d, %d) %d' % (pos_line, pos_row, 2)
        if self.shadow[self.row*pos_line + pos_row] & 2 != 0 and pos_row-1 >= 0 and house_now[pos_line][pos_row-1] >= 0:
            no_shadow = False#flag for not use shadow because eye analyse
            house_left = copy.deepcopy(house_now)
            num_map_left = copy.deepcopy(num_map_now)
            inc = 1
            while pos_row-inc >= 0 and house_left[pos_line][pos_row-inc] >= 0:
                num_map_left['num_'+str(house_left[pos_line][pos_row-(inc-1)])] -= 1
                num_map_left['num_'+str(-1)] += 1
                house_left[pos_line][pos_row-(inc-1)] = -1
                this_shadow_line[2] += 1
                inc+=1
            #recount value
            for i in [pos_line-1, pos_line, pos_line+1] if pos_line-1>=0 and pos_line+1<self.line else [pos_line-1, pos_line] if pos_line-1>0 else [pos_line, pos_line+1] if pos_line+1<self.line else [pos_line,]:
                for j in range(pos_row-inc if pos_row-inc>=0 else 0, (pos_row+2) if pos_row+1<self.row else self.row):
                    if house_left[i][j] >= 0:
                        self.pos_count(house_left, i, j, num_map_left)
                        if house_left[i][j] == 0 or house_left[i][j] == 1:
                            no_shadow = True
            self.history = self.history[:depth-1]+'l'
            if depth % 100 == 0:
                #print self.history
                pass
            #print_house(house_left)
            self.house_list = self.house_list[:depth]+[(house_left,num_map_left),]
            result = self.travel(pos_line, pos_row-(inc-1), depth+1)
            shadow_line_excluded = self.excludeShadowLeft(((pos_line, pos_row-this_shadow_line[2]), (pos_line, pos_row)), result[1])
            #print result[1], shadow_line_excluded
            if no_shadow is False and shadow_line_excluded is not None:
                with self.shadow.get_lock():
                    for step in range(shadow_line_excluded[0][1], shadow_line_excluded[1][1]+1):
                        self.shadow[self.row*step + pos_row] &= 13
            if result[0]:
                return result

        #move right
        #if self.shadow[pos_line][pos_row][3] == 0:
        #    print 'shadow (%d, %d) %d' % (pos_line, pos_row, 3)
        if self.shadow[self.row*pos_line + pos_row] & 1 != 0 and pos_row+1 < self.row and house_now[pos_line][pos_row+1] >= 0:
            no_shadow = False#flag for not use shadow because eye analyse
            house_right = copy.deepcopy(house_now)
            num_map_right = copy.deepcopy(num_map_now)
            inc = 1
            while pos_row+inc < self.row and house_right[pos_line][pos_row+inc] >= 0:
                num_map_right['num_'+str(house_right[pos_line][pos_row+(inc-1)])] -= 1
                num_map_right['num_'+str(-1)] += 1
                house_right[pos_line][pos_row+(inc-1)] = -1
                this_shadow_line[3] += 1
                inc+=1
            #recount value
            for i in [pos_line-1, pos_line, pos_line+1] if pos_line-1>=0 and pos_line+1<self.line else [pos_line-1, pos_line] if pos_line-1>0 else [pos_line, pos_line+1] if pos_line+1<self.line else [pos_line,]:
                for j in range(pos_row-1 if pos_row-1>0 else 0, (pos_row+inc) if pos_row+inc<self.row else self.row):
                    if house_right[i][j] >= 0:
                        self.pos_count(house_right, i, j, num_map_right)
                        if house_right[i][j] == 0 or house_right[i][j] == 1:
                            no_shadow = True
            self.history = self.history[:depth-1]+'r'
            if depth % 100 == 0:
                #print self.history
                pass
            #print_house(house_right)
            self.house_list = self.house_list[:depth]+[(house_right,num_map_right),]
            result = self.travel(pos_line, pos_row+(inc-1), depth+1)
            shadow_line_excluded = self.excludeShadowRight(((pos_line, pos_row), (pos_line, pos_row+this_shadow_line[3])), result[1])
            #print result[1], shadow_line_excluded
            if no_shadow is False and shadow_line_excluded is not None:
                with self.shadow.get_lock():
                    for step in range(shadow_line_excluded[0][1], shadow_line_excluded[1][1]+1):
                        self.shadow[self.row*step + pos_row] &= 14
            if result[0]:
                return result

        return result

    # move from (pos_line, pos_row)
    # return (result, (ul, dr))
    def travel(self, pos_line, pos_row, depth):

        result = (False, ((0, 0), (0, 0)))
        this_shadow = ((pos_line, pos_row), (pos_line, pos_row))#ul, dr
        this_shadow_line = [0, 0, 0, 0]#for up, down, left, right count
        a_house, a_num_map = self.house_list[depth-1]
        house_now = copy.deepcopy(a_house)
        num_map_now = copy.deepcopy(a_num_map)
        ok = self.are_you_ok(house_now, pos_line, pos_row, num_map_now, depth)
        if ok==False:
            result = (False, ((pos_line, pos_row), (pos_line, pos_row)))
            return result
        elif ok==True:
            result = (True, ((pos_line, pos_row), (pos_line, pos_row)))
            return result
        #return None

        #move up
        if pos_line-1 >= 0 and house_now[pos_line-1][pos_row] >= 0:
            house_up = copy.deepcopy(house_now)
            num_map_up = copy.deepcopy(num_map_now)
            inc = 1
            while pos_line-inc >= 0 and house_up[pos_line-inc][pos_row] >= 0:
                num_map_up['num_'+str(house_up[pos_line-(inc-1)][pos_row])] -= 1
                num_map_up['num_'+str(-1)] += 1
                house_up[pos_line-(inc-1)][pos_row] = -1
                this_shadow_line[0] += 1
                inc+=1
            #recount value
            for i in range(pos_line-inc if pos_line-inc>=0 else 0, (pos_line+2) if pos_line+1<self.line else self.line):
                for j in [pos_row-1, pos_row, pos_row+1] if pos_row-1>=0 and pos_row+1<self.row else [pos_row-1, pos_row] if pos_row-1>0 else [pos_row, pos_row+1] if pos_row+1<self.row else [pos_row,]:
                    if house_up[i][j] >= 0:
                        self.pos_count(house_up, i, j, num_map_up)
            self.history = self.history[:depth-1]+'u'
            if depth % 100 == 0:
                #print self.history
                pass
            #print_house(house_up)
            self.house_list = self.house_list[:depth]+[(house_up,num_map_up),]
            result = self.travel(pos_line-(inc-1), pos_row, depth+1)
            this_shadow = self.mergeShadow(self.mergeShadow(((pos_line - this_shadow_line[0], pos_row), (pos_line, pos_row)), result[1]), this_shadow)
            #if depth == 2:
            #    print 'lgbu', pos_line, pos_row, this_shadow
            if result[0]:
                result = (True, this_shadow)
                return result

        #move down
        if pos_line+1 < self.line and house_now[pos_line+1][pos_row] >= 0:
            house_down = copy.deepcopy(house_now)
            num_map_down = copy.deepcopy(num_map_now)
            inc = 1
            while pos_line+inc < self.line and house_down[pos_line+inc][pos_row] >= 0:
                num_map_down['num_'+str(house_down[pos_line+(inc-1)][pos_row])] -= 1
                num_map_down['num_'+str(-1)] += 1
                house_down[pos_line+(inc-1)][pos_row] = -1
                this_shadow_line[1] += 1
                inc+=1
            #recount value
            for i in range(pos_line-1 if pos_line-1>=0 else 0, (pos_line+inc) if pos_line+inc<self.line else self.line):
                for j in [pos_row-1, pos_row, pos_row+1] if pos_row-1>=0 and pos_row+1<self.row else [pos_row-1, pos_row] if pos_row-1>0 else [pos_row, pos_row+1] if pos_row+1<self.row else [pos_row,]:
                    if house_down[i][j] >= 0:
                        self.pos_count(house_down, i, j, num_map_down)
            self.history = self.history[:depth-1]+'d'
            if depth % 100 == 0:
                #print self.history
                pass
            #print_house(house_down)
            self.house_list = self.house_list[:depth]+[(house_down,num_map_down),]
            result = self.travel(pos_line+(inc-1), pos_row, depth+1)
            this_shadow = self.mergeShadow(self.mergeShadow(((pos_line, pos_row), (pos_line + this_shadow_line[1], pos_row)), result[1]), this_shadow)
            #if depth == 2:
            #    print 'lgbd', pos_line, pos_row, this_shadow
            if result[0]:
                result = (True, this_shadow)
                return result

        #move left
        if pos_row-1 >= 0 and house_now[pos_line][pos_row-1] >= 0:
            house_left = copy.deepcopy(house_now)
            num_map_left = copy.deepcopy(num_map_now)
            inc = 1
            while pos_row-inc >= 0 and house_left[pos_line][pos_row-inc] >= 0:
                num_map_left['num_'+str(house_left[pos_line][pos_row-(inc-1)])] -= 1
                num_map_left['num_'+str(-1)] += 1
                house_left[pos_line][pos_row-(inc-1)] = -1
                this_shadow_line[2] += 1
                inc+=1
            #recount value
            for i in [pos_line-1, pos_line, pos_line+1] if pos_line-1>=0 and pos_line+1<self.line else [pos_line-1, pos_line] if pos_line-1>0 else [pos_line, pos_line+1] if pos_line+1<self.line else [pos_line,]:
                for j in range(pos_row-inc if pos_row-inc>=0 else 0, (pos_row+2) if pos_row+1<self.row else self.row):
                    if house_left[i][j] >= 0:
                        self.pos_count(house_left, i, j, num_map_left)
            self.history = self.history[:depth-1]+'l'
            if depth % 100 == 0:
                #print self.history
                pass
            #print_house(house_left)
            self.house_list = self.house_list[:depth]+[(house_left,num_map_left),]
            result = self.travel(pos_line, pos_row-(inc-1), depth+1)
            this_shadow = self.mergeShadow(self.mergeShadow(((pos_line, pos_row - this_shadow_line[2]), (pos_line, pos_row)), result[1]), this_shadow)
            #if depth == 2:
            #    print 'lgbl', pos_line, pos_row, depth, this_shadow, result[1]
            if result[0]:
                result = (True, this_shadow)
                return result

        #move right
        if pos_row+1 < self.row and house_now[pos_line][pos_row+1] >= 0:
            house_right = copy.deepcopy(house_now)
            num_map_right = copy.deepcopy(num_map_now)
            inc = 1
            while pos_row+inc < self.row and house_right[pos_line][pos_row+inc] >= 0:
                num_map_right['num_'+str(house_right[pos_line][pos_row+(inc-1)])] -= 1
                num_map_right['num_'+str(-1)] += 1
                house_right[pos_line][pos_row+(inc-1)] = -1
                this_shadow_line[3] += 1
                inc+=1
            #recount value
            for i in [pos_line-1, pos_line, pos_line+1] if pos_line-1>=0 and pos_line+1<self.line else [pos_line-1, pos_line] if pos_line-1>0 else [pos_line, pos_line+1] if pos_line+1<self.line else [pos_line,]:
                for j in range(pos_row-1 if pos_row-1>0 else 0, (pos_row+inc) if pos_row+inc<self.row else self.row):
                    if house_right[i][j] >= 0:
                        self.pos_count(house_right, i, j, num_map_right)
            self.history = self.history[:depth-1]+'r'
            if depth % 100 == 0:
                #print self.history
                pass
            #print_house(house_right)
            self.house_list = self.house_list[:depth]+[(house_right,num_map_right),]
            result = self.travel(pos_line, pos_row+(inc-1), depth+1)
            this_shadow = self.mergeShadow(self.mergeShadow(((pos_line, pos_row), (pos_line, pos_row - this_shadow_line[3])), result[1]), this_shadow)
            #if depth == 2:
            #    print 'lgbr', pos_line, pos_row, depth, this_shadow, result[1]
            if result[0]:
                result = (True, this_shadow)
                return result

        result = (False, this_shadow)
        return result

    def mergeShadow(self, sa, sb):
        sr = ((sa[0][0] if sa[0][0]<sb[0][0] else sb[0][0], sa[0][1] if sa[0][1]<sb[0][1] else sb[0][1]), (sa[1][0] if sa[1][0]>sb[1][0] else sb[1][0], sa[1][1] if sa[1][1]>sb[1][1] else sb[1][1]))
        return sr

    def excludeShadowUp(self, l, s):
        if l[1][0] > s[1][0]:
            return ((s[1][0]+1, l[1][1]), (l[1][0], l[1][1]))
        return None

    def excludeShadowDown(self, l, s):
        if l[0][0] < s[0][0]:
            return ((l[0][0], l[0][1]), (s[0][0]-1, l[0][1]))
        return None

    def excludeShadowLeft(self, l, s):
        if l[1][1] > s[1][1]:
            return ((l[1][0], s[1][1]+1), (l[1][0], l[1][1]))
        return None

    def excludeShadowRight(self, l, s):
        if l[0][1] < s[0][1]:
            return ((l[0][0], l[0][1]), (l[0][0], s[0][1]-1))
        return None


def driver_init():
    global driver
    driver = webdriver.Chrome()


def driver_quit():
    global driver
    driver.quit()


def driver_login():
    global driver

    driver.get('http://www.qlcoder.com/auth/login')
    time.sleep(1)
    driver.maximize_window()
    time.sleep(1)
    driver.find_element_by_xpath("//input[@id='email']").send_keys('mrujowfi@163.com')
    time.sleep(1)
    driver.find_element_by_xpath("//input[@id='password']").send_keys('kzchmwdi10')
    time.sleep(1)
    driver.find_element_by_xpath("//input[@id='login-submit']").click()
    time.sleep(3)


def driver_getQuestion():
    global driver

    driver.get('http://www.qlcoder.com/train/autocr')
    time.sleep(3)

    content = ''
    while content == '':
        time.sleep(1)
        print 'wait for page'
        content = driver.find_element_by_xpath("//body").text

    if content.__contains__(u'请先登陆'):
        driver_login()
        return driver_getQuestion()
    else:
        question = content.split('\n')[7]
        return question


def driver_sendAnswer(ans):
    global driver

    driver.get(ans)
    time.sleep(3)
    content = driver.find_element_by_xpath("//body").text
    if content.__contains__(u'请先登陆'):
        driver_login()
        driver_sendAnswer(ans)


def make_args(dev, turn_index):
    result = dict()
    result['result'] = multiprocessing.Queue(maxsize=5)
    result['data_lock'] = multiprocessing.RLock()
    if dev:
        result['arg'] = '''
level=20&x=9&y=11&map=110000000000001100000000010010000000001100000011111000000000000000000100000000100010000000000001000
'''
    else:
        result['arg'] = driver_getQuestion()
    arg = result['arg'][:30]
    line = int(arg.split('&')[1].split('=')[1])
    row = int(arg.split('&')[2].split('=')[1])
    result['shadow'] = multiprocessing.Array(ctypes.c_byte, [15 for i in range(line*row)])

    result['queue'] = multiprocessing.Queue(maxsize=-1)
    result['queue_reverse'] = multiprocessing.Queue(maxsize=-1)
    if turn_index == 0:
        result['start_pos'] = (0, 0)
    else:
        result['start_pos'] = (0, 0)
    # print 'start_pos: %d, %d' % (result['start_pos'][0], result['start_pos'][1])

    result['count_wall'] = multiprocessing.Array(ctypes.c_int32, [-1 for i in range(line*row)])
    result['syn'] = multiprocessing.Value(ctypes.c_byte, 0)
    result['q_wc'] = multiprocessing.Queue(maxsize=-1)  # wait count
    result['q_hc'] = multiprocessing.Array(ctypes.c_int32, [-1 for i in range(line*row)])  # have counted
    result['n_wp'] = multiprocessing.Value(ctypes.c_int32, 0)
    result['q_wp'] = multiprocessing.Array(Point, [(-1, -1, -1) for i in range(line*row)])  # wait for picking
    result['n_hp'] = multiprocessing.Value(ctypes.c_int32, 0)
    result['q_hp'] = multiprocessing.Array(Point, [(-1, -1, -1) for i in range(line*row)])  # have picked
    result['proc_num'] = 1  # num of all proc
    result['wait_num'] = multiprocessing.Value(ctypes.c_int32, 0)  # num of proc waiting
    result['sum_walk'] = multiprocessing.Value(ctypes.c_int32, 0)  # num of proc waiting
    result['rule'] = multiprocessing.Array(ctypes.c_int32, [-1, -1, -1])
    result['percent'] = 0.05  # percent of not any test points nearby(9*9) the result point

    return result


if __name__ == '__main__':
    dev = True
    if dev is False:
        driver_init()
    try:
        m = 0
        for i in range(100):
            dict_args = make_args(dev, i)

            #create processes
            processed = []
            for j1 in range(dict_args['proc_num']):
                dict_args['mission_type'] = j1
                dict_args['reverse'] = 0
                processed.append(ProcRobot(dict_args))

            #start processes
            for k in range(len(processed)):
                processed[k].daemon = True
                processed[k].start()
                # time.sleep(1)

            #join processes
            # for i in range(len(processed)):
            #     processed[i].join()

            # why always last proc failed to kill himself...
            while True:
                time.sleep(15)
                alive = 0
                index = -1
                for l in range(len(processed)):
                    if processed[l].is_alive():
                        index = l
                        alive += 1
                if alive == 0:
                    break
                elif len(processed) > 1 and alive == 1:
                    processed[index].terminate() # sometime terminate a last process doing the right pos
                    break
                else:
                    # print 'walk alive %d %d' % (alive, m)
                    pass
                m += 1

            ans = ''
            if dict_args['result'].qsize() == 1:
                ans = dict_args['result'].get()
            else:
                print 'all failed'

            if dev:
                break
            elif ans != '':
                driver_sendAnswer(ans)

    except Exception, e:
        print 'error', e
        time.sleep(1)
        print traceback.format_exc()
    if dev is False:
        driver_quit()
