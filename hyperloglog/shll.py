"""
Sliding HyperLogLog
"""

import math
import heapq
from hashlib import sha1
from itertools import chain
from hll import get_treshold, estimate_bias, get_alpha, get_rho

class SlidingHyperLogLog(object):
    """
    Sliding HyperLogLog: Estimating cardinality in a data stream (Telecom ParisTech)
    """

    __slots__ = ('window', 'alpha', 'p', 'm', 'LPFM')

    def __init__(self, error_rate, window, lpfm=None):
        """
        Implementes a Sliding HyperLogLog

        error_rate = abs_err / cardinality
        """

        self.window = window

        if lpfm is not None:
             m = len(lpfm)
             p = int(round(math.log(m, 2)))

             if (1 << p) != m:
                 raise ValueError('List length is not power of 2')
             self.LPFM = lpfm

        else:
            if not (0 < error_rate < 1):
                raise ValueError("Error_Rate must be between 0 and 1.")

            # error_rate = 1.04 / sqrt(m)
            # m = 2 ** p

            p = int(math.ceil(math.log((1.04 / error_rate) ** 2, 2)))
            m = 1 << p
            self.LPFM = [[] for i in range(m)]

        self.alpha = get_alpha(p)
        self.p = p
        self.m = m

    @classmethod
    def from_list(cls, lpfm, window):
        return cls(None, window, lpfm)

    def add(self, timestamp, value):
        """
        Adds the item to the HyperLogLog
        """
        # h: D -> {0,1} ** 64
        # x = h(v)
        # j = <x_0x_1..x_{p-1})>
        # w = <x_{p}x_{p+1}..>
        # <t_i, rho(w)>

        x = long(sha1(value).hexdigest()[:16], 16)
        j = x & (self.m - 1)
        w = x >> self.p
        R = get_rho(w, 64 - self.p)

        Rmax = None
        tmp = []
        tmax = None
        tmp2 = list(heapq.merge(self.LPFM[j], [(timestamp, R)]))

        for t, R in reversed(tmp2):
                if tmax is None:
                    tmax = t

                if t < (tmax - self.window):
                    break

                if R > Rmax:
                    tmp.append((t, R))
                    Rmax = R

        tmp.reverse()
        self.LPFM[j] = tmp

    def update(self, *others):
        """
        Merge other counters
        """

        for item in others:
            if self.m != item.m:
                raise ValueError('Counters precisions should be equal')

        for j in xrange(len(self.LPFM)):
            Rmax = None
            tmp = []
            tmax = None
            tmp2 = list(heapq.merge(*([item.LPFM[j] for item in others] + [self.LPFM[j]])))

            for t, R in reversed(tmp2):
                if tmax is None:
                    tmax = t

                if t < (tmax - self.window):
                    break

                if R > Rmax:
                    tmp.append((t, R))
                    Rmax = R

            tmp.reverse()
            self.LPFM[j] = tmp

    def __eq__(self, other):
        if self.m != other.m:
            raise ValueError('Counters precisions should be equal')

        return self.LPFM == other.LPFM

    def __ne__(self, other):
        return not self.__eq__(other)

    def __len__(self):
        raise NotImplemented

    def card(self, timestamp, window=None):
        """
        Returns the estimate of the cardinality at 'timestamp' using 'window'
        """
        if window is None:
            window = self.window

        if not 0 < window <= self.window:
            raise ValueError('0 < window <= W')

        M = [max(chain((R for ts, R in lpfm if ts >= (timestamp - window)), iter([0]))) for lpfm in self.LPFM]

        E = self.alpha * float(self.m ** 2) / sum(math.pow(2.0, -x) for x in M)
        Ep = (E - estimate_bias(E, self.p)) if E <= 5 * self.m else E

        #count number or registers equal to 0
        V = M.count(0)
        H = self.m * math.log(self.m / float(V)) if V > 0 else Ep
        return H if H <= get_treshold(self.p) else Ep

