import weakref
import threading
import traceback
import collections

class EventBus:
    '''
    A synapse EventBus provides an easy way manage callbacks.
    '''

    def __init__(self):
        self.isfini = False
        self.finievt = threading.Event()

        self._syn_meths = collections.defaultdict(list)
        self._syn_weaks = collections.defaultdict(weakref.WeakSet)

        self._fini_meths = []
        self._fini_weaks = weakref.WeakSet()

    def synOn(self, name, meth, weak=False):
        '''
        Add a callback method to the SynCallBacker.

        Example:

            def baz(event):
                x = event[1].get('x')
                y = event[1].get('y')
                return x + y

            d.synOn('woot',baz)

            d.synFire('foo',10,20)

        Notes:

            * Callback convention is decided by synFire caller
            * Use weak=True to hold a weak reference to the method.

        '''
        if weak:
            self._syn_weaks[name].add(meth)
            return

        self._syn_meths[name].append(meth)

    def synFire(self, name, **info):
        '''
        Fire each of the methods registered for an FIXME.
        Returns a list of the return values of each method.

        Example:

            for ret in d.synFire('woot',foo='asdf'):
                print('got: %r' % (ret,))

        '''
        event = (name,info)
        return self.synDist(event)

    def synDist(self, event):
        '''
        Distribute an existing event tuple.
        '''
        ret = []
        name = event[0]
        meths = self._syn_meths.get(name)
        if meths != None:
            for meth in meths:
                try:
                    ret.append( meth( event ) )
                except Exception as e:
                    traceback.print_exc()

        weaks = self._syn_weaks.get(name)
        if weaks != None:
            for meth in weaks:
                try:
                    ret.append( meth( event ) )
                except Exception as e:
                    traceback.print_exc()

        return ret

    def synFini(self):
        '''
        Fire the 'fini' handlers and set self.isfini.

        Example:

            d.synFini()

        '''
        self.isfini = True

        for meth in self._fini_meths:
            try:
                meth()
            except Exception as e:
                traceback.print_exc()

        for meth in self._fini_weaks:
            try:
                meth()
            except Exception as e:
                traceback.print_exc()

        self.finievt.set()

    def synOnFini(self, meth, weak=False):
        '''
        Register a handler to fire when this EventBus shuts down.
        '''
        if weak:
            return self._fini_weaks.add(meth)
        self._fini_meths.append(meth)

    def synWait(self, timeout=None):
        '''
        Wait for synFini() on the EventBus.

        Example:

            d.synWait()

        '''
        return self.finievt.wait(timeout=timeout)