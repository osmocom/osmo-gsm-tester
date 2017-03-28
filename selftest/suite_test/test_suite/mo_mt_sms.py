nitb_iface = resources.nitb_iface()
nitb = resources.nitb()
bts = resources.bts()
ms_mo = resources.modem()
ms_mt = resources.modem()

nitb.start(nitb_iface)
bts.start(nitb)

nitb.add_subscriber(ms_mo, resources.msisdn())
nitb.add_subscriber(ms_mt, resources.msisdn())

ms_mo.start()
ms_mt.start()
wait(nitb.subscriber_attached, ms_mo, ms_mt)

sms = ms_mo.sms_send(ms_mt.msisdn)
wait(nitb.sms_received, sms)
