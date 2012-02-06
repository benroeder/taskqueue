#!/usr/bin/ruby

#require 'rubygems'

require 'yajl/json_gem'
require 'ruote'
require 'ruote/storage/fs_storage'
require 'ruote-amqp'

require 'mq'

STDOUT.sync = true

$engine = Ruote::Engine.new(
    Ruote::Worker.new(Ruote::FsStorage.new('work')))

#$engine.noisy = true

#AMQP.logging = true
AMQP.settings[:host] = 'localhost'
AMQP.settings[:user] = 'wfworker'
AMQP.settings[:pass] = 'wfworker'
AMQP.settings[:vhost] = '/wfworker'

# We run under daemontools and it communicates via signals
Signal.trap('SIGTERM') do
    puts 'Shutdown gracefully'
    $engine.shutdown
    puts 'Asked engine to stop'
end

# This spawns a thread which listens for amqp responses
RuoteAMQP::Receiver.new( $engine, :launchitems => true )

class FakeParticipant
    include Ruote::LocalParticipant
    def consume(workitem)
        puts workitem.inspect
        puts "workitem consumed"
        reply_to_engine(workitem)
    end
end

$engine.register_participant :fake1, FakeParticipant
$engine.register_participant :hardworker, RuoteAMQP::ParticipantProxy, :queue => 'taskqueue'

pdef = Ruote.process_definition do
    fake1
end

wfid = $engine.launch(pdef, :f1 => "qwerty")

puts "Engine running"
$engine.join()
puts "Engine stopped"
#RuoteAMQP.stop!