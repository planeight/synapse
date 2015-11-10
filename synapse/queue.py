import time
import threading

from synapse.common import *
from synapse.eventbus import EventBus

class QueueShutdown(Exception): pass

class BulkQueue(EventBus):
    '''
    A Queue like object which returns lists of items at once.
    ( to minimize round trips in remote queue retrieval )

    Example:

        q = BulkQueue()

        for x in q.get():
            stuff(x)

    Notes:

        * specify fd for a previously "hybernating" queue.

    '''
    def __init__(self, fd=None):
        EventBus.__init__(self)
        self.fd = fd
        self.last = time.time()
        self.lock = threading.Lock()

        self.items = []
        self.event = threading.Event()
        self.onfini( self._onQueFini )

    def _onQueFini(self):
        self.event.set()
        if self.fd != None:
            self.fd.close()

    def abandoned(self, dtime):
        now = time.time()
        return now > (self.last + dtime)

    def hyber(self, fd):
        '''
        Tell the queue to go into a "hybernation" state where
        items are written to fd using msgpack.

        Any subsequent call to get() will "wake" and load the queue.
        '''
        with self.lock:
            self.fd = fd
            [ fd.write(msgenpack(i)) for i in self.items ]
            self.items = None

    def _check_hyber(self, x):
        # check for hybernation
        if self.fd:
            self.fd.write( msgenpack(x) )
            return True

    def prepend(self, x):
        '''
        Prepend and item to the front of the queue.

        Example:

            q.prepend( x )

        Notes:

            * this is currently heavy and should be used judiciously...
            * if the queue is hybernating, it's the same as append

        '''
        # NOTE: this is heavy, use judiciously
        if self.isfini:
            raise QueueShutdown()

        with self.lock:
            if self._check_hyber(x):
                return

            self.items.insert(0,x)
            self.event.set()

    def extend(self, x):
        '''
        Bulk add a list of objects to the queue.

        Example:

            x = [ "foo", "bar", "baz" ]
            q.extend( x )

        '''
        if self.isfini:
            raise QueueShutdown()

        with self.lock:
            if self.fd != None:
                [ self.fd.write(msgenpack(i)) for i in x ]
                return

            self.items.extend(x)
            self.event.set()

    def __len__(self):
        return len(self.items)

    def __iter__(self):
        try:
            while True:
                for i in self.get(timeout=1):
                    yield i
        except QueueShutdown as e:
            pass

    def put(self, item):
        '''
        Put an item into the BulkQueue.

        Example:

            q.put( foo )

        '''
        if self.isfini:
            raise QueueShutdown()

        with self.lock:
            if self._check_hyber(item):
                return

            self.items.append(item)
            self.event.set()

    def get(self, timeout=None):
        '''
        Retrieve the next list of items from the BulkQueue.

        Example:

            for item in q.get():
                dostuff(item)

        '''
        self.last = time.time()
        with self.lock:

            # were we hybernated?
            if self.fd:
                # ghetto for now... maybe back them better later
                self.fd.seek(0)
                byts = self.fd.read()

                unpk = msgpack.Unpacker(use_list=False, encoding='utf8')
                unpk.feed(byts)

                self.items = [ x for x in unpk ]

                self.fd.close()
                self.fd = None

            if self.items:
                return self._get_items()

            if self.isfini:
                raise QueueShutdown()

            # Clear the event so we can wait...
            self.event.clear()

        self.event.wait(timeout=timeout)
        if self.isfini:
            raise QueueShutdown()

        with self.lock:
            self.last = time.time()
            if not self.items and self.isfini:
                raise QueueShutdown()
            return self._get_items()

    def peek(self):
        return list(self.items)

    def __len__(self):
        return len(self.items)

    def _get_items(self):
        ret = self.items
        self.items = []
        return ret