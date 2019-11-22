""" Implements quantum circuits and circuit-valued monoidal functors.

>>> from discopy import Pregroup, Word, Cup, Wire
>>> s, n = Pregroup('s'), Pregroup('n')
>>> Alice = Word('Alice', n)
>>> loves = Word('loves', n.r @ s @ n.l)
>>> Bob = Word('Bob', n)
>>> grammar = Cup(n) @ Wire(s) @ Cup(n.l)
>>> sentence = grammar << Alice @ loves @ Bob
>>> ob = {s: 0, n: 1, n.l: 1, n.r: 1}
>>> ob.update({w.dom: 0 for w in [Alice, loves, Bob]})
>>> ar = {Alice: Ket(0),
...       loves: CX << Ket(0, 0),
...       Bob: Ket(0),
...       Cup(n): CX >> Bra(0, 0),
...       Cup(n.l): CX >> Bra(0, 0)}
>>> F = CircuitFunctor(ob, ar)
>>> F(sentence).eval()
Matrix(dom=Dim(1), cod=Dim(1), array=[1])
"""

import numpy as np
from discopy.cat import fold, Quiver
from discopy.moncat import Ob, Ty, Box, Diagram, MonoidalFunctor
from discopy.matrix import Dim, Matrix, MatrixFunctor


class PRO(Ty):
    """ Implements the objects of a PRO, i.e. a non-symmetric PROP.
    Wraps a natural number n into a unary type Ty(1, ..., 1) of length n.

    >>> PRO(1) @ PRO(1)
    PRO(2)
    >>> assert PRO(3) == Ty(1, 1, 1)
    """
    def __init__(self, n):
        """
        >>> list(PRO(0))
        []
        >>> list(PRO(1))
        [Ob(1)]
        >>> assert all(len(PRO(n)) == n for n in range(5))
        """
        n = n if isinstance(n, int) else len(n)
        super().__init__(*(n * [Ob(1)]))

    def __repr__(self):
        """
        >>> PRO(0), PRO(1)
        (PRO(0), PRO(1))
        """
        return "PRO({})".format(len(self))

    def __str__(self):
        """
        >>> print(PRO(2 * 3 * 7))
        PRO(42)
        """
        return repr(self)

    def __add__(self, other):
        """
        >>> sum((PRO(n) for n in range(5)), PRO(0))
        PRO(10)
        """
        return PRO(len(self) + len(other))

    def __getitem__(self, key):
        """
        >>> PRO(42)[2:4]
        PRO(2)
        >>> assert all(PRO(42)[i] == Ob(1) for i in range(42))
        """
        if isinstance(key, slice):
            return PRO(len(super().__getitem__(key)))
        return super().__getitem__(key)

class Circuit(Diagram):
    """ Implements quantum circuits as diagrams.

    >>> circuit = CX >> CX >> CX >> CX >> CX >> CX
    >>> assert np.all(circuit.eval() == Id(2).eval())
    """
    def __init__(self, dom, cod, gates, offsets):
        """
        >>> c = Circuit(2, 2, [CX, CX], [0, 0])
        """
        self._gates = gates
        super().__init__(PRO(dom), PRO(cod), gates, offsets)

    @property
    def gates(self):
        """
        >>> Circuit(1, 1, [X, X], [0, 0]).gates
        [Gate('X', 1, [0, 1, 1, 0]), Gate('X', 1, [0, 1, 1, 0])]
        """
        return self._gates

    def __repr__(self):
        """
        >>> Circuit(2, 2, [CX, CX], [0, 0])  # doctest: +ELLIPSIS
        Circuit(2, 2, [Gate('CX', 2, [...]), Gate('CX', 2, [...])], [0, 0])
        """
        return "Circuit({}, {}, {}, {})".format(
            len(self.dom), len(self.cod), self.gates, self.offsets)

    def then(self, other):
        """
        >>> print(SWAP >> CX)
        SWAP >> CX
        """
        r = super().then(other)
        return Circuit(len(r.dom), len(r.cod), r.boxes, r.offsets)

    def tensor(self, other):
        """
        >>> print(CX @ H)
        CX @ Id(1) >> Id(2) @ H
        """
        r = super().tensor(other)
        return Circuit(len(r.dom), len(r.cod), r.boxes, r.offsets)

    def dagger(self):
        """
        >>> print((CX >> SWAP).dagger())
        SWAP.dagger() >> CX.dagger()
        """
        r = super().dagger()
        return Circuit(len(r.dom), len(r.cod), r.boxes, r.offsets)

    @staticmethod
    def id(n):
        """
        >>> Circuit.id(2)
        Id(2)
        """
        return Id(n)

    def eval(self):
        """ Evaluates the circuit as a discopy Matrix.

        >>> assert np.all((Ket(0, 0) >> SWAP).eval() == Ket(0, 0).eval())
        >>> assert np.all((Ket(0, 1) >> SWAP).eval() == Ket(1, 0).eval())
        >>> assert np.all((Ket(1, 0) >> SWAP).eval() == Ket(0, 1).eval())
        >>> assert np.all((Ket(1, 1) >> SWAP).eval() == Ket(1, 1).eval())

        >>> assert np.all((Ket(0, 0) >> CX).eval() == Ket(0, 0).eval())
        >>> assert np.all((Ket(0, 1) >> CX).eval() == Ket(0, 1).eval())
        >>> assert np.all((Ket(1, 0) >> CX).eval() == Ket(1, 1).eval())
        >>> assert np.all((Ket(1, 1) >> CX).eval() == Ket(1, 0).eval())

        >>> for U in [SWAP, X, Y, Z, S >> S, CX >> CX >> CX]:
        ...     assert np.all((U >> U.dagger()).eval() == Id(len(U.dom)).eval())
        >>> for U in [H, T >> T >> T >> T]:
        ...     assert np.allclose((U >> U.dagger()).eval(), Id(len(U.dom)).eval())
        """
        F_eval = MatrixFunctor({PRO(1): 2}, Quiver(lambda x: x.array))
        return F_eval(self)

    def to_tk(self):
        """ Returns a pytket circuit.

        >>> c = Circuit(3, 3, [SWAP, Rx(0.25), CX], [0, 1, 1]).to_tk()
        >>> list(c)
        [SWAP q[0], q[1];, Rx(0.25PI) q[1];, CX q[1], q[2];]
        """
        import pytket as tk
        c = tk.Circuit(len(self.dom))
        for g, n in zip(self.gates, self.offsets):
            if g.data:
                if g.name not in ['Rx', 'Rz']:
                    raise NotImplementedError
                c.__getattribute__(g.name)(
                    *(n + i for i in range(len(g.dom))), g.data['phase'])
            else:
                c.__getattribute__(g.name)(*(n + i for i in range(len(g.dom))))
        return c

def from_tk(c):
    """ Takes a pytket circuit and returns a planar circuit,
    SWAP gates are introduced when applying gates to non-adjacent qubits.

    >>> c1 = Circuit(3, 3, [SWAP, Rx(0.25), CX], [0, 1, 1])
    >>> c2 = from_tk(c1.to_tk())
    >>> assert c1 == c2  # This works as long as there are no interchangers!
    """
    def gates_from_tk(g):
        name = g.op.get_type().name
        if name == 'Rx':
            return Rx(g.op.get_params()[0])
        if name == 'Rz':
            return Rz(g.op.get_params()[0])
        return {g.name: g for g in [SWAP, CX, H, S, T, X, Y, Z]}[name]
    gates, offsets = [], []
    for g in c.get_commands():
        i0 = g.qubits[0].index
        for i, q in enumerate(g.qubits[1:]):
            if q.index == i0 + i + 1:
                break  # gate applies to adjacent qubit already
            elif q.index < i0 + i + 1:
                for j in range(q.index, i0 + i):
                    gates.append(SWAP)
                    offsets.append(j)
                if q.index <= i0:
                    i0 -= 1  # we just swapped q to the right of q0
            elif q.index > i0 + i + 1:
                for j in range(q.index - i0 + i - 1):
                    gates.append(SWAP)
                    offsets.append(q.index - j - 1)
        gates.append(gates_from_tk(g))
        offsets.append(i0)
    return Circuit(c.n_qubits, c.n_qubits, gates, offsets)

def Euler(a, b, c):
    """ Returns a 1-qubit Euler decomposition with angles 2 * pi * a, b, c.

    >>> print(Euler(1, 0, 1))
    Rx(1) >> Rz(0) >> Rx(1)
    >>> assert np.allclose(Euler(1, 0, 1).eval(), Id(1))
    """
    return Circuit(1, 1, [Rx(a), Rz(b), Rx(c)], [0, 0, 0])

def random(n_qubits, depth=0, gateset=[], seed=None):
    """ Returns a random Euler decomposition if n_qubits == 1,
    otherwise returns a random tiling with the given depth and gateset.

    >>> c = random(1, seed=420)
    >>> [g.data['phase'] for g in c.gates]  # doctest: +ELLIPSIS
    [0.02..., 0.78..., 0.27...]
    >>> c.eval().array[0]  # doctest: +ELLIPSIS
    array([ 0.64...+0.06...j, -0.05...-0.76...j])
    >>> c.eval().array[1]  # doctest: +ELLIPSIS
    array([-0.73...-0.20...j,  0.06...-0.64...j ])
    >>> print(random(2, 2, [CX, H, T], seed=420))
    CX >> T @ Id(1) >> Id(1) @ T
    >>> print(random(3, 2, [CX, H, T], seed=420))
    CX @ Id(1) >> Id(2) @ T >> H @ Id(2) >> Id(1) @ H @ Id(1) >> Id(2) @ H
    """
    import random
    if seed:
        random.seed(seed)
    if n_qubits == 1:
        return Euler(
            random.random(), random.random(), random.random())
    U = Id(n_qubits)
    for d in range(depth):
        L, affected = Id(0), 0
        while affected <= n_qubits - 2:
            gate = random.choice(gateset)
            L = L @ gate
            affected += gate.n_qubits
        if n_qubits - affected == 1:
            L = L @ random.choice([g for g in gateset if g.n_qubits == 1])
        U = U >> L
    return U

class Id(Circuit):
    """ Implements identity circuit on n qubits.

    >>> c = CX @ H >> T @ SWAP
    >>> assert Id(3) >> c == c == c >> Id(3)
    """
    def __init__(self, n):
        """
        >>> assert Circuit.id(42) == Id(42) == Circuit(42, 42, [], [])
        """
        if isinstance(n, PRO):
            n = len(n)
        Diagram.__init__(self, PRO(n), PRO(n), [], [])

    def __repr__(self):
        """
        >>> Id(42)
        Id(42)
        """
        return "Id({})".format(len(self.dom))

    def __str__(self):
        """
        >>> print(Id(42))
        Id(42)
        """
        return repr(self)

class Gate(Box, Circuit):
    """ Implements quantum gates as boxes in a circuit diagram.

    >>> CX
    Gate('CX', 2, [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 1, 0, 0, 1, 0])
    >>> Rx(0.25)  # doctest: +ELLIPSIS
    Gate('Rx', 1, [0.7..., -0.7...j, -0.7...j, 0.7...], data={'phase': 0.25})
    """
    def __init__(self, name, n_qubits, array, data={}, _dagger=False):
        """
        >>> g = Rx(0.25)
        >>> assert g == Rx(0.25)
        >>> assert g.dom == g.cod == PRO(1)
        """
        self.n_qubits, self._array = n_qubits, array
        Box.__init__(self, name, PRO(n_qubits), PRO(n_qubits),
                     data=data, _dagger=_dagger)

    @property
    def array(self):
        """
        >>> X.array
        [0, 1, 1, 0]
        """
        return self._array

    def __repr__(self):
        """
        >>> CX
        Gate('CX', 2, [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 1, 0, 0, 1, 0])
        >>> Rx(0.25)  # doctest: +ELLIPSIS
        Gate('Rx', 1, [...], data={'phase': 0.25})
        """
        if self._dagger:
            return repr(self.dagger()) + '.dagger()'
        return "Gate({}, {}, {}{})".format(
            repr(self.name), len(self.dom), repr(self.array),
            ', data=' + repr(self.data) if self.data else '')

    def __str__(self):
        """
        >>> print(CX)
        CX
        >>> print(Rx(0.25))
        Rx(0.25)
        """
        if self._dagger:
            return str(self.dagger()) + '.dagger()'
        if self.name in ['Rx', 'Rz']:
            return "{}({})".format(self.name, self.data['phase'])
        return self.name

    def dagger(self):
        """
        >>> print(CX.dagger())
        CX.dagger()
        >>> print(Rx(0.25).dagger())
        Rx(0.25).dagger()
        """
        return Gate(self.name, self.n_qubits, self.array,
                    data=self.data, _dagger=not self._dagger)

class Ket(Gate):
    """ Implements ket for a given bitstring.

    >>> Ket(1, 1, 0).eval()
    Matrix(dom=Dim(1), cod=Dim(2, 2, 2), array=[0, 0, 0, 0, 0, 0, 1, 0])
    """
    def __init__(self, *bitstring):
        """
        >>> g = Ket(1, 1, 0)
        """
        self.bitstring = bitstring
        Box.__init__(self, 'Ket({})'.format(', '.join(map(str, bitstring))),
                     PRO(0), PRO(len(bitstring)))

    def __repr__(self):
        """
        >>> Ket(1, 1, 0)
        Ket(1, 1, 0)
        """
        return self.name


    def dagger(self):
        """
        >>> Ket(0, 1).dagger()
        Bra(0, 1)
        """
        return Bra(*self.bitstring)

    @property
    def array(self):
        """
        >>> Ket(0).eval()
        Matrix(dom=Dim(1), cod=Dim(2), array=[1, 0])
        >>> Ket(0, 1).eval()
        Matrix(dom=Dim(1), cod=Dim(2, 2), array=[0, 1, 0, 0])
        """
        m = Matrix(Dim(1), Dim(1), [1])
        for b in self.bitstring:
            m = m @ Matrix(Dim(1), Dim(2), [0, 1] if b else [1, 0])
        return m.array

class Bra(Gate):
    """ Implements bra for a given bitstring.

    >>> Bra(1, 1, 0).eval()
    Matrix(dom=Dim(2, 2, 2), cod=Dim(1), array=[0, 0, 0, 0, 0, 0, 1, 0])
    >>> assert all((Bra(x, y, z) << Ket(x, y, z)).eval() == 1
    ...            for x in [0, 1] for y in [0, 1] for z in [0, 1])
    """
    def __init__(self, *bitstring):
        """
        >>> g = Bra(1, 1, 0)
        """
        self.bitstring = bitstring
        Box.__init__(self, 'Bra({})'.format(', '.join(map(str, bitstring))),
                     PRO(len(bitstring)), PRO(0))

    def __repr__(self):
        """
        >>> Bra(1, 1, 0)
        Bra(1, 1, 0)
        """
        return self.name

    def dagger(self):
        """
        >>> Bra(0, 1).dagger()
        Ket(0, 1)
        """
        return Ket(*self.bitstring)

    @property
    def array(self):
        """
        >>> Bra(0).eval()
        Matrix(dom=Dim(2), cod=Dim(1), array=[1, 0])
        >>> Bra(0, 1).eval()
        Matrix(dom=Dim(2, 2), cod=Dim(1), array=[0, 1, 0, 0])
        """
        m = Matrix(Dim(1), Dim(1), [1])
        for b in self.bitstring:
            m = m @ Matrix(Dim(2), Dim(1), [0, 1] if b else [1, 0])
        return m.array

class CircuitFunctor(MonoidalFunctor):
    """ Implements funtors from monoidal categories to circuits

    >>> x, y, z = Ty('x'), Ty('y'), Ty('z')
    >>> f, g, h = Box('f', x, y + z), Box('g', z, y), Box('h', y + z, x)
    >>> d = (f @ Diagram.id(z)
    ...       >> Diagram.id(y) @ g @ Diagram.id(z)
    ...       >> Diagram.id(y) @ h)
    >>> ob = {x: 2, y: 1, z: 1}
    >>> ar = {f: SWAP, g: Rx(0.25), h: CX}
    >>> F = CircuitFunctor(ob, ar)
    >>> print(F(d))
    SWAP @ Id(1) >> Id(1) @ Rx(0.25) @ Id(1) >> Id(1) @ CX
    """
    def __init__(self, ob, ar):
        """
        >>> F = CircuitFunctor({}, {})
        """
        super().__init__({x: PRO(y) for x, y in ob.items()}, ar)

    def __repr__(self):
        """
        >>> CircuitFunctor({}, {})
        CircuitFunctor(ob={}, ar={})
        """
        return "CircuitFunctor(ob={}, ar={})".format(
            repr({x: len(y) for x, y in self.ob.items()}), repr(self.ar))

    def __call__(self, d):
        """
        >>> x = Ty('x')
        >>> F = CircuitFunctor({x: 1}, {})
        >>> assert isinstance(F(Diagram.id(x)), Circuit)
        """
        r = super().__call__(d)
        if isinstance(d, Diagram):
            return Circuit(len(r.dom), len(r.cod), r.boxes, r.offsets)
        return r

def Rx(phase):
    """
    >>> Rx(0.25)  # doctest: +ELLIPSIS
    Gate('Rx', 1, [0.7..., -0.7...j, -0.7...j, 0.7...], data={'phase': 0.25})
    """
    theta = 2 * np.pi * phase
    array = [np.cos(theta / 2), -1j * np.sin(theta / 2),
             -1j * np.sin(theta / 2), np.cos(theta / 2)]
    return Gate('Rx', 1, array, data={'phase': phase})

def Rz(phase):
    """
    >>> Rz(0.25)  # doctest: +ELLIPSIS
    Gate('Rz', 1, [1, 0, 0, ...1j...], data={'phase': 0.25})
    """
    theta = 2 * np.pi * phase
    array = [1, 0, 0, np.exp(1j * theta)]
    return Gate('Rz', 1, array, data={'phase': phase})

SWAP = Gate('SWAP', 2, [1, 0, 0, 0,
                        0, 0, 1, 0,
                        0, 1, 0, 0,
                        0, 0, 0, 1])
CX = Gate('CX', 2, [1, 0, 0, 0,
                    0, 1, 0, 0,
                    0, 0, 0, 1,
                    0, 0, 1, 0])
H = Gate('H', 1, 1 / np.sqrt(2) * np.array([1, 1, 1, -1]))
S = Gate('S', 1, [1, 0, 0, 1j])
T = Gate('T', 1, [1, 0, 0, np.exp(1j * np.pi / 4)])
X = Gate('X', 1, [0, 1, 1, 0])
Y = Gate('Y', 1, [0, -1j, 1j, 0])
Z = Gate('Z', 1, [1, 0, 0, -1])
