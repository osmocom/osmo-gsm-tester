ip_address = tenv.ip_address()
nitb = tenv.nitb()
bts = tenv.bts()
ms_ext = tenv.msisdn()
fake_ext = tenv.msisdn()
ms = tenv.modem()

nitb.configure(ip_address, bts)
bts.configure(nitb)

nitb.start()
bts.start()

nitb.add_fake_ext(fake_ext)
nitb.add_subscriber(ms, ms_ext)

ms.start()
wait(nitb.subscriber_attached, ms)
sms = ms.sms_send(fake_ext)
wait(nitb.sms_received, sms)
