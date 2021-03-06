"""
Taskqueue dispatcher daemon
"""

import sys
import logging
import pika

from taskqueue.daemonlib import Daemon
from taskqueue.workitem import get_workitem, WorkitemError, DEFAULT_CONTENT_TYPE
from taskqueue.confparser import SECTION_TASKQUEUE

LOG = logging.getLogger(__name__)

class Dispatcher(Daemon):
    """Dispatcher daemon"""

    pidfile = "/var/run/dispatcher.pid"

    def __init__(self, config):
        """Initialize application."""

        self.channel = None
        self.connection = None
        if not config.has_section(SECTION_TASKQUEUE):
            config.add_section(SECTION_TASKQUEUE)
        super(Dispatcher, self).__init__(config)

    def handle_delivery(self, channel, method, header, body):
        """Handle delivery from WFE."""
        LOG.debug("Method: %r" % method)
        LOG.debug("Header: %r" % header)
        LOG.debug("Body: %r" % body)
        settings = dict(self.config.items(SECTION_TASKQUEUE))

        try:
            workitem = get_workitem(header, body,
                                    settings.get('workitem_type_map', None),
                                    settings.get('default_workitem_type',
                                                 DEFAULT_CONTENT_TYPE))
        except WorkitemError as err:
            # Report error and accept message
            LOG.error("%s" % err)
            channel.basic_ack(method.delivery_tag)
            return

        worker = workitem.worker_type
        channel.basic_publish(exchange='',
                              routing_key='worker_%s' % worker,
                              body=body,
                              properties=pika.BasicProperties(
                                  delivery_mode=2,
                                  content_type=header.content_type
                              ))

        channel.basic_ack(method.delivery_tag)

    def run(self):
        """Event cycle."""

        LOG.debug("create connection")
        self.connection = pika.BlockingConnection(self.amqp_params)
        LOG.debug("dispatcher connected")
        self.channel = self.connection.channel()
        self.channel.queue_declare(queue="taskqueue", durable=True,
                                   exclusive=False, auto_delete=False)
        self.channel.basic_consume(self.handle_delivery, queue="taskqueue")
        self.channel.start_consuming()

    def cleanup(self, signum, frame):
        """Handler for termination signals."""

        LOG.debug("cleanup")
        self.channel.stop_consuming()
        self.connection.close()
        sys.exit(0)
