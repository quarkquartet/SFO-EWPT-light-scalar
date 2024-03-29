"""
This file write the effective potential in high-T expansion.
Author: Isaac Wang
Requires package of cosmoTransitions.
"""

import numpy as np
from cosmoTransitions import generic_potential as gp
from cosmoTransitions import pathDeformation as pd
from cosmoTransitions import helper_functions
from scipy import optimize

# -----------------------------------------------------------------
# Physical Constants
# -----------------------------------------------------------------
GF = 1.16637e-05  # Fermi Constant
v = 1 / (np.sqrt(2 * np.sqrt(2) * GF))  # Higgs vev
mHSM = 125.13  # Higgs mass


# -----------------------------------------------------------------
# Transfer between physical parameters and bare parameters
# -----------------------------------------------------------------
def muH2(mS, sintheta):
    """\mu_H square"""
    return 0.5 * (mHSM**2 * (1 - sintheta**2) + mS**2 * sintheta**2)


def muS2(mS, sintheta):
    """\mu_S square"""
    return sintheta**2 * mHSM**2 + (1 - sintheta**2) * mS**2


def A(mS, sintheta):
    """A parameter"""
    nominator = (mHSM**2 - mS**2) * sintheta * np.sqrt(1 - sintheta**2)
    denominator = np.sqrt(2) * v
    return nominator / denominator


def lm(mS, sintheta):
    """\lambda parameter"""
    nominator = (1 - sintheta**2) * mHSM**2 + sintheta**2 * mS**2
    return nominator / (4 * v**2)


# -----------------------------------------------------------------
# Define effective potential
# -----------------------------------------------------------------
class model(gp.generic_potential):
    """Effective potential, and some defined functions."""

    def init(self, mS, sintheta):
        self.Ndim = 2
        self.Tmax = 100
        self.mS = mS
        self.sintheta = sintheta
        self.lm = lm(self.mS, self.sintheta)
        self.A = A(self.mS, self.sintheta)
        self.muH2 = muH2(self.mS, self.sintheta)
        self.muS2 = muS2(self.mS, self.sintheta)
        self.g = 0.65
        self.gY = 0.36
        self.yt = 0.9945
        self.D = (3 * self.g**2 + self.gY**2 + 4 * self.yt**2) / 16.0
        self.E = (2 * self.g**3 + (self.g**2 + self.gY**2) ** (3 / 2)) / (
            48 * np.pi
        )
        self.cs = 1.0 / 3
        self.Deff = self.D - self.cs * self.A**2 / (4.0 * self.muS2)
        self.lmeff = self.lm - self.A**2 / (2 * self.muS2)
        self.T0 = np.sqrt(
            0.5 * self.muH2 - v**2 * self.A**2 / (2 * self.muS2)
        ) / np.sqrt(self.D - self.cs * self.A**2 / (4 * self.muS2))
        self.Tc = self.T0 * np.sqrt(
            (self.Deff * self.lmeff) / (-self.E**2 + self.Deff * self.lmeff)
        )
        self.strength = 2 * self.E / self.lmeff
        self.Tn = False
        self.non_restore_trigger = self.Deff * self.lmeff - self.E**2

    def Vtot(self, X, T, include_radiation=True):
        T = np.asanyarray(T, dtype=float)
        X = np.asanyarray(X, dtype=float)
        T2 = (T * T) + 1e-100
        phi1 = X[..., 0]
        phi2 = X[..., 1]
        y = self.D * T2 * phi1**2 - 0.5 * self.muH2 * phi1**2
        y += -self.E * T * phi1**3
        y += 0.25 * self.lm * phi1**4
        y += (
            0.5 * self.muS2 * phi2**2
            - 0.5 * self.A * (phi1**2 + self.cs * T2 - 2 * v**2) * phi2
        )
        return y

    def truevev(self, T):
        assert T < self.Tc
        nominator = 3.0 * T * self.E + np.sqrt(
            9.0 * self.E**2 * T**2
            + 8.0 * self.Deff * (self.T0**2 - T**2) * self.lmeff
        )
        denominator = 2.0 * self.lmeff
        return nominator / denominator

    def Spath(self, X, T):
        X = np.asanyarray(X)
        T = np.asanyarray(T)
        phi1 = X[..., 0]
        T2 = (T * T) + 1e-100
        return 0.5 * self.A * (phi1**2 + self.cs * T2 - 2 * v**2) / self.muS2

    def tunneling_at_T(self, T):
        assert T < self.Tc

        def V_(x, T=T, V=self.Vtot):
            return V(x, T)

        def dV_(x, T=T, dV=self.gradV):
            return dV(x, T)

        # tobj = pd.fullTunneling([self.findMinimum(T=T),[0,self.Spath([0],T)]],V_,dV_)
        tobj = pd.fullTunneling(
            [
                [self.truevev(T=T), self.Spath([self.truevev(T=T)], T)],
                [1e-100, self.Spath([1e-100], T)],
            ],
            V_,
            dV_,
        )
        return tobj

    def findTn(self):
        if self.strength >= 12:
            Tmax = 0.95 * self.Tc
        elif self.strength >= 4:
            Tmax = 0.99 * self.Tc
        else:
            Tmax = self.Tc
        eps = 0.01
        if self.mS <= 0.1:
            first = 0.05
        elif self.mS <= 1:
            first = 0.02
        else:
            first = 0.01

        def nuclea_trigger(Tv):
            ST = self.tunneling_at_T(T=Tv).action / Tv
            return ST - 140.0

        for i in range(0, 1000):
            Ttest = Tmax - first - i * eps
            print("Tunneling at T=" + str(Ttest))
            trigger = nuclea_trigger(Ttest)
            print("S3/T-140=" + str(trigger))
            if trigger < 0.0:
                break
        Tmin = Ttest
        print("Tnuc should be within " + str(Tmin) + " and " + str(Tmin + eps))
        self.Tn = optimize.brentq(
            nuclea_trigger, Tmin + eps, Tmin, disp=False, xtol=1e-5, rtol=1e-6
        )

    def strength_Tn(self):
        if not self.Tn:
            self.findTn()
        Tnuc = self.Tn
        return self.truevev(T=Tnuc) / Tnuc

    def beta_over_H_at_Tn(self):
        "Ridders algorithm"
        if not self.Tn:
            self.findTn()
        Tnuc = self.Tn
        print("Tnuc = " + str(Tnuc))
        if self.Tc - Tnuc >= 0.002:
            eps = 0.001
        elif self.Tc - Tnuc >= 0.0002:
            eps = 0.0001
        else:
            eps = 0.00001

        def SoverT(Tv):
            ST = self.tunneling_at_T(T=Tv).action / Tv
            return ST

        dev = (
            SoverT(Tnuc - 2.0 * eps)
            - 8.0 * SoverT(Tnuc - eps)
            + 8.0 * SoverT(Tnuc + eps)
            - SoverT(Tnuc + 2.0 * eps)
        ) / (12.0 * eps)
        return dev * Tnuc

    def alpha(self):
        if not self.Tn:
            self.findTn()
        Tnuc = self.Tn
        if self.Tc - Tnuc >= 0.002:
            eps = 0.001
        else:
            eps = 0.99 * (self.Tc - Tnuc) / 2

        def deltaV(T):
            falsev = [0, self.Spath([0], T)]
            truev = self.findMinimum(T=T)
            return self.Vtot(falsev, T) - self.Vtot(truev, T)

        dev = (
            deltaV(Tnuc - 2 * eps)
            - 8.0 * deltaV(Tnuc - eps)
            + 8.0 * deltaV(Tnuc + eps)
            - deltaV(Tnuc + 2.0 * eps)
        ) / (
            12.0 * eps
        )  # derivative of deltaV w.r.t T at Tn
        latent = deltaV(Tnuc) - 0.25 * Tnuc * dev
        rho_crit = np.pi**2 * 106.75 * Tnuc**4 / 30.0
        return latent / rho_crit


class model1d(gp.generic_potential):
    def init(self, mS, sintheta):
        self.Ndim = 1
        self.Tmax = 100
        self.mS = mS
        self.sintheta = sintheta
        self.lm = lm(self.mS, self.sintheta)
        self.A = A(self.mS, self.sintheta)
        self.muH2 = muH2(self.mS, self.sintheta)
        self.muS2 = muS2(self.mS, self.sintheta)
        self.g = 0.65
        self.gY = 0.36
        self.yt = 0.9945
        self.D = (3 * self.g**2 + self.gY**2 + 4 * self.yt**2) / 16.0
        self.E = (2 * self.g**3 + (self.g**2 + self.gY**2) ** (3 / 2)) / (
            48 * np.pi
        )
        self.cs = 1.0 / 3
        self.Deff = self.D - self.cs * self.A**2 / (4.0 * self.muS2)
        self.lmeff = self.lm - self.A**2 / (2 * self.muS2)
        self.T0 = np.sqrt(
            0.5 * self.muH2 - v**2 * self.A**2 / (2 * self.muS2)
        ) / np.sqrt(self.D - self.cs * self.A**2 / (4 * self.muS2))
        self.Tc = self.T0 * np.sqrt(
            (self.Deff * self.lmeff) / (-self.E**2 + self.Deff * self.lmeff)
        )
        self.strength = 2 * self.E / self.lmeff
        self.Tn = False

    def Vtot(self, X, T, include_radiation=True):
        T = np.asanyarray(T, dtype=float)
        X = np.asanyarray(X, dtype=float)
        T2 = (T * T) + 1e-100
        phi1 = X[..., 0]
        y = (
            self.Deff * T2 * phi1**2
            - (0.5 * self.muH2 - 0.5 * v**2 * self.A**2 / (self.muS2)) * phi1**2
        )
        y += -self.E * T * phi1**3
        y += 0.25 * self.lmeff * phi1**4
        return y

    def truevev(self, T):
        assert T < self.Tc
        nominator = 3.0 * T * self.E + np.sqrt(
            9.0 * self.E**2 * T**2
            + 8.0 * self.Deff * (self.T0**2 - T**2) * self.lmeff
        )
        denominator = 2.0 * self.lmeff
        return nominator / denominator

    def tunneling_at_T(self, T):
        assert T < self.Tc

        def V_(x, T=T, V=self.Vtot):
            return V(x, T)

        def dV_(x, T=T, dV=self.gradV):
            return dV(x, T)

        tobj = pd.fullTunneling([[self.truevev(T)], [1e-100]], V_, dV_)
        return tobj

    def findTn(self):
        # eps = 0.01
        if self.mS <= 0.1:
            eps = 0.03
        elif self.mS <= 1:
            eps = 0.02
        else:
            eps = 0.01

        def nuclea_trigger(Tv):
            ST = self.tunneling_at_T(T=Tv).action / Tv
            return ST - 140.0

        for i in range(1, 1000):
            if nuclea_trigger(self.Tc - i * eps) <= 0.0:
                break
        Tn1 = self.Tc - (i - 1) * eps
        self.Tn = optimize.brentq(nuclea_trigger, Tn1, Tn1 - eps, disp=False)

    def strength_Tn(self):
        if not self.Tn:
            self.findTn()
        Tnuc = self.Tn
        return self.truevev(T=Tnuc) / Tnuc

    def beta_over_H_at_Tn(self):
        "Ridders algorithm"
        if not self.Tn:
            self.findTn()
        Tnuc = self.Tn
        if self.Tc - Tnuc >= 0.002:
            eps = 0.001
        elif self.Tc - Tnuc >= 0.0002:
            eps = 0.0002
        else:
            eps = 0.00001

        def SoverT(Tv):
            ST = self.tunneling_at_T(T=Tv).action / Tv
            return ST

        dev = (
            SoverT(Tnuc - 2.0 * eps)
            - 8.0 * SoverT(Tnuc - eps)
            + 8.0 * SoverT(Tnuc + eps)
            - SoverT(Tnuc + 2.0 * eps)
        ) / (12.0 * eps)
        return dev * Tnuc

    def alpha(self):
        if not self.Tn:
            self.findTn()
        Tnuc = self.Tn
        if self.Tc - Tnuc >= 0.002:
            eps = 0.001
        else:
            eps = 0.99 * (self.Tc - Tnuc) / 2

        def deltaV(T):
            falsev = [0.0]
            truev = self.truevev(T)
            return self.Vtot(falsev, T) - self.Vtot(truev, T)

        dev = (
            deltaV(Tnuc - 2 * eps)
            - 8.0 * deltaV(Tnuc - eps)
            + 8.0 * deltaV(Tnuc + eps)
            - deltaV(Tnuc + 2.0 * eps)
        ) / (
            12.0 * eps
        )  # derivative of deltaV w.r.t T at Tn
        latent = deltaV(Tnuc) - 0.25 * Tnuc * dev
        rho_crit = np.pi**2 * 106.75 * Tnuc**4 / 30.0
        return latent / rho_crit
