ip_address = tenv.ip_address()
nitb = tenv.nitb()
bts = tenv.bts()
ms_mo = tenv.modem()
ms_mt = tenv.modem()

nitb.start(ip_address)
bts.start(nitb)

nitb.add_subscriber(ms_mo, tenv.msisdn())
nitb.add_subscriber(ms_mt, tenv.msisdn())

ms_mo.start()
ms_mt.start()
wait(nitb.subscriber_attached, ms_mo, ms_mt)

sms = ms_mo.sms_send(ms_mt)
wait(nitb.sms_received, sms)
