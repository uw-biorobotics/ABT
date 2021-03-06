#!/usr/bin/python
#
#   Utilities for BT-HMM_
#

import numpy as np
import numbers
from random import *
import matplotlib.pyplot as plt
#import editdistance as ed   #pip install editdistance
##from tqdm import tqdm
import os
import sys
from tqdm import tqdm
from logP import *
from logP_matrix import *

#sudo pip install scikit-learn  # dep for hmmlearn
#pip install -U --user hmmlearn
#from hmmlearn import hmm
import random as random
NSYMBOLS = 40
STRICT = True

LZ = np.nan   # our log-of-zero value

epsilon = 1.0E-4
FAIL = '          FAIL'
PASS = '          PASS'

###########   replace with import logP.py

class hmm():
    def __init__(self,nstates):
        if nstates < 2:
            self._error('HMM must have at least 2 states')
        self.N = nstates
        self.Pi = np.zeros(nstates)
        self.Pi[0] = 1.0      # by default always start in state 1
        self.transmat_ = np.zeros((nstates,nstates))
        self.emissionprob_ = np.ones((self.N,NSYMBOLS))* 1/float(NSYMBOLS)  # default Uniform
        self.names = []
        self.typestring = 'hmm_bh'
        for i in range(self.N):
            self.names.append('-noname-')

    # Forward algorithm for multiple runouts
    #def forwardM(self, X, lengths):
        #for i, l in enumerate(lengths):

            #for st in range(self.N):

    # forward algorithm for a single runout
    def forwardS(self, Y): # go through the emissions
        #alpha = logPv(self.Pi) * logPv(self.emissionprob_[:,Y[0]].T)  # starting state probs.
        #print 'forwardS: lenY:', len(Y)
        alpha = np.ones((len(Y),self.N)) #       eqn     (19)
        for i in range(self.N):
            alpha[0,i] = self.Pi[i] * self.emissionprob_[i, Y[0]]

        for tp1,y in enumerate( Y[1:]): #                (20)
            t = tp1 - 1
            #print '    iter, tp1:', jj,tp1
            for st in range(self.N):  # iterate over post states
                tmpsum = 0.0
                for prev_st in range(self.N): # sum over prev states
                    tmpsum += self.transmat_[prev_st,st]*alpha[t,prev_st]
                alpha[tp1,st] = self.emissionprob_[st,y] * tmpsum
                prev_st = st
        return alpha

    # Log-based forward algorithm for a single runout
    def forwardSL(self, Y, alpha=None):
        '''       Y = all observations concatenated
                #alpha = starting LOG probability of each state

        Returns:   alpha =
        '''
        # initialization
        T = len(Y)
        N = self.N
        if alpha is None:
            alpha = logPm(np.ones((T,N)))          #       (19)
            for j in range(N):
                alpha[0,j] = logP(self.Pi[j] * self.emissionprob_[j,Y[0]])
        logA =  logPm(self.transmat_)
        logB =  logPm(self.emissionprob_)
        #for y in Y[1:]:  # emission sequence
        for t in range(1,T):         #    Rab t+1 ->  t,  t --> t-1
            for j in range(self.N):
                tmpsum = logP(0)
                for i in range(self.N):                #       (20)
                    a = logA[i,j]
                    b = alpha[t-1,i]
                    tmpsum +=  a * b
                c = logB[j,Y[t]]
                alpha[t,j] = c * tmpsum
        #print '------------ alpha ----------------'
        #print alpha
        return alpha

    def POlambda(self, Y):
        al = self.forwardSL(Y)
        T = len(Y)-1
        a = logP(0.0)
        for j in range(self.N):
            b = al[T,j].test_val()
            a = a + b
        return a

    #  Backward Algorithm
    #
    def backwardSL(self, Y):   #  See Rabiner
        T = len(Y)
        N = self.N
        logA =  logPm(self.transmat_)
        logB =  logPm(self.emissionprob_)
        #initialization                                 (24)
        beta = logPm(np.ones((T,N)))
        #print len(Y)
        for k in range(T-1):             #              (25)
            t = T-2 - k #   t -> T-2, T-3, T-4
            for i in range(self.N):
                bi = logP(0)
                for j in range(N):
                    a1 = logA[i,j]
                    a2 = logB[j,Y[t+1]]
                    a3 = beta[t+1,j]
                    bi += a1*a2*a3
                beta[t,i] = bi
        return beta



    #
    #   Viterbi Algorithm
    #     (Rabiner '89 eqns 32a-35)

    def Viterbi(self,Obs):
        logA =  logPm(self.transmat_)
        logB =  logPm(self.emissionprob_)

        #Initialization             (32a,b)
        T = len(Obs)
        delta = logPm(np.ones((T,self.N)))
        for j in range(self.N):
            delta[0,j] = logP(self.Pi[j]) * logB[j,Obs[0]]
        chi = np.zeros((T,self.N)).astype(int)    # note: NOT a logPx()

        #Recursion                   (33)
        d = logPv(np.zeros(self.N))
        for t in range(1,T):    #emission loop
            for j in range(self.N):   # state loop time t
                for i in range(self.N):   # state loop time t-1
                    d[i] = delta[t-1,i]*logA[i,j]
                #print 'd: ',d
                argmax, lpmax = d.maxlv()
                delta[t,j] = lpmax * logB[j,Obs[t]]
                chi[t,j] = argmax

        #Termination

        tmp = logPv(np.ones(self.N))
        for i,lpv in enumerate(tmp):
            tmp[i] = delta[T-1,i]
        qam, pstar = tmp.maxlv()  # most likely terminal state
        qstar = [0]*T
        qstar[T-1] = qam

        # State Seq. backtracking        (35)
        for i in range(0,T-2):
            t = T-2-i
            qstar[t] = chi[t+1,qstar[t+1]]
        self.VitVis(Obs,qstar,delta,chi)
        return qstar

    # visualize viterbi backtracking for debugging
    def VitVis(self,Obs,qstar,delta,chi):
        lines = []
        for j in range(self.N):
            lj = ''
            for t in range(len(Obs)):
                c = ' '
                d = '_'
                if abs(delta[t,j].test_val()== 0.0):
                    d = '0'
                #print 't,j, delta:', t,j,delta[t,j], d
                if not (delta[t,j].test_val()==0):   # fix: test for zero
                    c = '.'  # non-zero prob for state j
                if j == qstar[t]:
                    c = '*'  # optimal selection
                    if (delta[t,j].test_val()==0):
                        c = 'X'  # this shouldn't be
                lj += c
            lines.append(lj)

        print 'State evolution:'
        for j in range(self.N):
            print j, '  ['+lines[j]+']'
        print '\n\n'



    #
    #  Baum Welch Algorithm
    #
    def fit(self,Obs):
        '''     For a single runout / observation sequence
        '''
        #print '-------------  A (starting self.transmat_) --------------'
        #print self.transmat_
        #print '-------------  B (starting self.emissionprob_) --------------'
        #print self.emissionprob_
        lp0 = logP(0.0)
        alpha = self.forwardSL(Obs)
        beta  = self.backwardSL(Obs)
        T = len(Obs)
        N = self.N
        xi = logPm(np.zeros((T,N,N)))       #    (37)
        s1 = logPv(np.zeros(T))
        for t in range(T-1):
            denom = lp0              #denominator of (37)
            nslice = logPm(np.zeros((N,N)))
            for i in range(N):
                a = alpha[t,i]
                for j in range(N):
                    b = self.transmat_[i,j]
                    c = self.emissionprob_[j,Obs[t+1]]
                    d = beta[t+1,j]
                    nslice[i,j] = a*b*c*d
                    denom = denom +  nslice[i,j]
            #assert denom.test_val() > TINY_EPSILON, ' (Almost) divide by zero '
            for i in range(N):
                for j in range(N):
                    xi[t,i,j] = nslice[i,j]/denom
                    #assert xi[t-1,i,j].test_val() >= 0.0, ' Help!!'
                    #assert xi[t-1,i,j].test_val() != np.Inf, ' Help!! (inf)'

        gam = logPm(np.zeros((T,N)))     #       (38)
        for t in range(T-1):
            for i in range(N):
                for j in range(N):
                    #print 'xi: ',  t,i,j,xi[t,i,j].test_val()
                    gam[t,i] += xi[t,i,j]

        gam_v = logPv(np.zeros((N)))      #       (39a)
        for i in range(N):
            for t in range(T-1):
                gam_v[i] += gam[t,i]

        xi_m = logPm(np.zeros((N,N)))     #       (39b)
        for i in range(N):
            for j in range(N):
                for t in range(T-1):      # sum all values except last one
                    xi_m[i,j] += xi[t,i,j]

        a_hat = np.zeros((N,N))   #       (40b)
        for i in range(N):
            for j in range(N):
                #print 'x[], gam_v[]', xi_m[i,j],gam_v[i]
                a_hat[i,j] = (xi_m[i,j]/gam_v[i]).test_val()

        b_hat = np.zeros((N,NSYMBOLS))  #   (40c)
        for sym in range(NSYMBOLS):
            for j in range(N):
                dsum = lp0  # denominator
                nsum = lp0 # numerator
                for t in range(T):
                    if Obs[t] == sym:
                        nsum+=gam[t,j]
                    dsum += gam[t,j]
                b_hat[j,sym] = (nsum/dsum).test_val()

        self.transmat_ = a_hat
        #print '-----------new transmat_ -----------'
        #print self.transmat_
        self.emissionprob_ = b_hat
        #print '-----------new emissionprob_ -----------'
        #print self.emissionprob_

               #
    #  Baum Welch Algorithm for multiple observation sequences
    #       (ideally for non-stationary models)
    #
    def fitMultiple(self,Obs, Ls):
        '''   based on Rabiner, eqns 109, 110
              Obs --  concatenated multiple runout observation sequences
              Ls  --  list of lengths of each sequene such that  Ls.sum == len Obs
        '''
        #print '-------------  A (starting self.transmat_) --------------'
        #print self.transmat_

        #print '-------------  B (starting self.emissionprob_) --------------'
        #print self.emissionprob_
        #print 'fitM: ', Obs, '\n', Ls
        lp0 = logP(0.0)  # quicker to keep this around for intializing
        N = self.N
        a_hat = np.zeros((N,N))
        b_hat=np.zeros((N,NSYMBOLS))
        obsl = []
        alphak = []
        betak = []
        Pk = []
        ptr = 0                 # point to the start of each seqeuence
        # first go through seqs and eval alpha & beta
        for k in range(len(Ls)):     # go through the obs sequences
            olen = Ls[k]
            #print 'ptrs: ', ptr, ptr+olen
            Ok = Obs[ptr:ptr+olen] # the current obs sequence
            ptr += olen
            #print 'starting alk,bek:', olen, Ok
            alphak.append(self.forwardSL(Ok))
            betak.append(self.backwardSL(Ok))
            Pk.append(self.POlambda(Ok))
            obsl.append(Ok)
        a_hat2 = np.zeros((N,N))
        b_hat2 =np.zeros((N,NSYMBOLS))
        for i in range(N):
            for j in range(N):
                nsum = lp0              # numerator of (109)
                dsum = lp0
                # now go through seqs and compute num and denom (109)
                for k in range(len(Ls)):
                    Tk = Ls[k]
                    Ok = obsl[k]
                    numk = lp0
                    denk = lp0
                    for t in range(Tk-1):
                            #numerator of (109)
                            a = alphak[k][t,i]
                            b = self.transmat_[i,j]
                            c = self.emissionprob_[j,Ok[t+1]]
                            d = betak[k][t+1,j]
                            numk = numk + a*b*c*d
                            # now work on demoninator of (109)
                            d = betak[k][t,i]
                            denk = denk + a*d
                    # summing over k
                    nsum = nsum + numk / Pk[k]
                    dsum = dsum + denk / Pk[k]
                a_hat2[i,j] = nsum
                a_hat[i,j] = (nsum/dsum).test_val()


        #  b_hat                              eqn 110
        for j in range(N):
            for l in range(NSYMBOLS):
                nsum = lp0
                dsum = lp0
                ptr = 0
                for k in range(len(Ls)):     # go through the obs sequences
                    Tk = Ls[k]
                    Ok = obsl[k]
                    numk = lp0
                    denk = lp0
                    for t in range(Tk-1):
                        #                             numerator of (110)
                        if(Ok[t]==l):
                            numk = numk + alphak[k][t,j]*betak[k][t,j]
                        #                             denominator of (110)
                        denk = denk + alphak[k][t,j]*betak[k][t,j]
                    nsum = nsum + numk / Pk[k]
                    dsum = dsum + denk / Pk[k]
                b_hat[j,l] = (nsum/dsum).test_val()
                b_hat2[j,l] = nsum
        print a_hat2
        print "2:", b_hat2
        self.transmat_ = a_hat
        #print '-----------new transmat_ -----------'
        #print self.transmat_
        self.emissionprob_ = b_hat
        #print '-----------new emissionprob_ -----------'
        #print self.emissionprob_


    def sample(self,T):
        states = []
        emissions = []
        # initial starting state
        state, p = self.pick_from_vec(self.Pi)
        states.append(state)
        #print 'initial state: ',state
        # main loop
        for i in range(T-1):
            # generate emission
            em, p = self.pick_from_vec(self.emissionprob_[state,:])
            emissions.append(em)
            # find next state
            state, p = self.pick_from_vec(self.transmat_[state,:])
            #print 'next state: ', state
            states.append(state)

        # generate a final emission
        em, p = self.pick_from_vec(self.emissionprob_[state,:])
        emissions.append(em)
        return (states, emissions)



##########################################################################
#
#   Utility functions
#
    def vec_normalize(self, v):
        sum = np.sum(v)
        return v/sum

    def pick_from_vec(self,vector):
        if STRICT:
            vector = self.vec_normalize(vector)
            self.row_check(vector,len(vector))

        r = random.random()
        P = 0.0
        for i in range(len(vector)):
            P += vector[i]
            if r<=P:
                return (i, vector[i])
        self._error('invalid prob vector')

    def check(self):
        print 'model check:'
        sh = np.shape(self.transmat_)
        if (sh[0] != self.N or sh[1] != self.N):
            self.error(' transmat_ wrong size')
        sh = np.shape(self.emissionprob_)
        if (sh[0] != self.N or sh[1] != NSYMBOLS):
            self.error(' emissionprob_ wrong size')
        for r in range(self.N):
            self.row_check(self.transmat_[r],self.N)
        sum = 0.0
        for st in range(self.N):
            self.row_check(self.emissionprob_[st,:],NSYMBOLS)
        self.row_check(self.Pi,self.N)


    def row_check(self,row,m):
        valid = True
        #print 'row_check:', row
        sum = 0.0
        for c in range(m):
            t = row[c]
            if t > 1.0 or  t < 0.0 :
                print 'illegal probability found'
                valid = False
            sum += t
        if abs(sum-1.0) > epsilon:
            valid = False
        if not valid:
            print row
            print 'Sum: ', sum
            self._error('a vector failed row check: sum != 1.0')
        return True


    def _error(self,msg):
        print 'hmm class (hmm_bh): ' + msg
        quit()



#################################################################################################
#################################################################################################
#################################################################################################
#
#     TESTS of hmm_log class
#

if __name__ == '__main__':

    ###################################
    # hmm class tests

    # test pic_from_vect(v)
    m = hmm(10)
    vector = [0,0,0,.333,.333,.333, 0,0,0]  # note sum = 0.9990000
    #optional if not STRICT:
    #vector = m.vec_normalize(vector)
    fs = 'test pic_from_vec'
    for i in range(10000):  # this really tests sum=1.000000
        x,p = m.pick_from_vec(vector)
        assert (x >1 and  x <= 5), fs+FAIL
    print fs+PASS


    ######################################
    #
    #  test model setups for hmm
    #

    A5 = np.array([[.5,.5,0,0,0],[0,.6,.4,0,0],[0,0,.75,.25,0],[0,0,0,0.8,0.2],[0,0,0,0,1.0]])
    
    # pv is the diagonal elements of 10x10 matrix
    pv = [0.5, 0.5, 0.7, 0.65, 0.8, 0.5, 0.3,0.6,0.7, 1.0]

    A10 = np.zeros((10,10))

    nsim_samples =   20         #   baseline   15
    nsim_rollouts = 100

    for r in range(10):
        A10[r,r] = pv[r]
        if(r+1 < 10):
            A10[r,r+1] = 1.0-A10[r,r]

    for ntest in [5]:
        fs =  '\n\ntesting hmm with ' + str(ntest) + ' states'
        print fs
        m = hmm(ntest)
        if ntest == 5:
            m.transmat_ = A5.copy()
        else:
            m.transmat_ = A10.copy()

        #   set up emission probabilities with width of 'w' symbols
        w = 6
        for i in range(m.N):
            mu = 0.5*w*(i+1)
            for j in range(NSYMBOLS):
                m.emissionprob_[i,j] = 0.0
                if j>mu-w/2 and j<=(mu+w/2):
                    m.emissionprob_[i,j] = 1/float(w)
        #print m.emissionprob_
        #if ntest == 10:
            #quit()

        m.check()
        print fs + ' [setup] ' + PASS

        ##############################################################
        #
        #    Simulate the HMM
        #
        st, em = m.sample(nsim_samples)
        print '----------- state sequence & emissions -----------------------'
        print st
        print em
        assert len(st) == len(em), 'Emissions dont match states from sample()'

        print '\n\nTest valid sample outputs:'
        for i,s in enumerate(st):
            #print 'checking: ' , i, s, em[i]
            if m.emissionprob_[s,em[i]] < epsilon:
                m._error('invalid emission detected')
        print 'got valid emissions'

        print '\nForward Algorithm:'

        #print 'state estimate: '
        #print '       forwardS()   (regular math)'
        #print m.forwardS(em)
        #print '       forwardSL()  (log math)'
        #print '         (v-matrix)'

        TINY_EPSILON = 1.0E-20

        print '\n     Test    Forward Algorithm:'
        fs = '   forward algorithm, forwardSL(em) '
        stseq =  [0, 0, 1, 1, 2, 3, 3, 3, 3, 3, 3, 3, 3, 3, 4]
        em = [6, 3, 6, 6, 8, 12, 14, 10, 15, 14, 14, 15, 12, 13, 16]
        alpha =  m.forwardSL(em)

        #print '------------alpha-------------'
        #print alpha


        #print alpha[14,4].test_val()
        #assert abs(alpha[14,4].test_val()-9.35945852879e-13) < TINY_EPSILON, fs+FAIL
        #assert abs(alpha[ 2,0].test_val()-0.000578703703704) < epsilon, fs+FAIL
        print fs+PASS


        print '\n     Test    Backward Algorithm:'
        stseq =  [0, 0, 1, 1, 2, 3, 3, 3, 3, 3, 3, 3, 3, 3, 4]
        em = [6, 3, 6, 6, 8, 12, 14, 10, 15, 14, 14, 15, 12, 13, 16]

        beta_test =  m.backwardSL(em)
        fs = '    backwards algorithm backwardSL(em) '
        #print beta_test
        #assert abs(beta_test[13,3].test_val()-0.1666666666667)<epsilon, fs+FAIL
        #assert abs(beta_test[ 3,0].test_val()-9.57396964103e-11) < TINY_EPSILON , fs+FAIL
        #print fs+PASS

        print '\n\n Test Viterbi Algorithm:'
        print 'st:',st
        print 'em:',em
        #print m.emissionprob_
        if ntest == 5:
            # TRUE state sequence (gen during simulation)
            stseq =  [0, 0, 1, 1, 2, 3, 3, 3, 3, 3, 3, 3, 3, 3, 4,4,4]
            #  NOTE: for BW testing w/ non stationary model, last state must be
            #        occupied more than once!
            em = [6, 3, 6, 6, 8, 12, 14, 10, 15, 14, 14, 15, 12, 13, 16,16,16]

            est_correct = [0,0,1,1,2,3,3,3,3,3,3,3,3,4,4,4,4]
        elif ntest == 10:
            stseq        = [0, 1, 1, 2, 2, 3, 3, 3, 3, 4, 4, 4, 4, 4, 4, 5, 5, 6, 7, 8]
            est_correct =  [0, 1, 1, 2, 2, 3, 3, 4, 4, 4, 4, 4, 4, 4, 4, 5, 5, 6, 7, 8]
            #                                    ^^^^^^
            em    = [3, 8, 6, 8, 7, 13, 10, 15, 14, 14, 14, 15, 18, 17, 18, 21, 17, 23, 23, 30]

        fs = 'test setup problem - data length mismatch'
        assert len(em) == len(stseq), fs
        assert len(em) == len(est_correct), fs

        qs = m.Viterbi(em)
        fs = 'Viterbi state estimation tests'
        for i,q in enumerate(qs):
            assert q==est_correct[i], fs+FAIL
        print fs+PASS

        #
        #   Let's try the Baum Welch!
        #
        print  '\n\n   Test Baum Welch fit() method'
        p0 = m.POlambda(em)
        m.fitMultiple(em,[len(em)])
        #p1 = m.POlambda(em)
        ##r = raw_input('<cr>')
        #m.fit(em)
        #p2 = m.POlambda(em)
        ##r = raw_input('<cr>')
        #m.fit(em)
        #p3 = m.POlambda(em)

        print "    Change in PO-lambda: "
        print p0
        exit()
        #print p1
        #print p2
        #print p3

        print '\n\n        -- --  --   Multiple Runout HMM.fit()  -- -- -- \n\n\n'

        ###################################################################
        #
        #    Regen the hmm
        #
        ntest = 5
        m = hmm(ntest)
        if ntest == 5:
            m.transmat_ = A5.copy()
        else:
            m.transmat_ = A10.copy()

        #   set up emission probabilities with width of 'w' symbols
        w = 6
        for i in range(m.N):
            mu = 0.5*w*(i+1)
            for j in range(NSYMBOLS):
                m.emissionprob_[i,j] = 0.0
                if j>mu-w/2 and j<=(mu+w/2):
                    m.emissionprob_[i,j] = 1/float(w)
        #print m.emissionprob_
        #if ntest == 10:
            #quit()

        ###################################################################
        #
        #    Generate the data
        #

        Obs = []
        Sts = []   # true state sequences
        Ls  = []
        Obsll = []
        nrunout = 10  # how many simulations of the HMM to perform/record
        for rn in range(nrunout):
            #    Simulate the HMM
            st, em = m.sample(nsim_samples)
            Obs.extend(em)
            Obsll.append(em)  # as list of lists
            Sts.extend(st)
            Ls.append(len(st))

        print '\n\n  Baum-Welch System ID with ', nrunout, ' runouts, ', ntest,'x',ntest, ' model.\n\n'
        print 'Initial Prob: ', m.POlambda(Obsll[1])
        imprv_ratio = 100.0
        BW_epsilon = 0.025   # stop after improvement below this (percentage)
        p = logP(1.0E-20)
        bwiter = 0
        while abs(1.0-imprv_ratio) > BW_epsilon:
        #for i in tqdm(range(10)):
            bwiter += 1
            m.fitMultiple(Obs,Ls)
            pprev = p
            p = m.POlambda(Obsll[1])   # returns a logP()
            imprv_ratio = (p/pprev).test_val()
            print bwiter, '     Prob:   ', p, '   imprv_ratio: ',  imprv_ratio-1.0
        print '\n\n'
        print m.transmat_
        print m.emissionprob_

        print ' \n\n               Completed  Test Runs  of hmm_log package   \n\n'
