nitb_iface = resources.nitb_iface()
nitb = resources.nitb()
bts = resources.bts()
ms_ext = resources.msisdn()
fake_ext = resources.msisdn()
ms = resources.modem()

nitb.configure(nitb_iface, bts)
bts.configure(nitb)

nitb.start()
bts.start()

nitb.add_fake_ext(fake_ext)
nitb.add_subscriber(ms, ms_ext)

ms.start()
wait(nitb.subscriber_attached, ms)
sms = ms.sms_send(fake_ext)
wait(nitb.sms_received, sms)
