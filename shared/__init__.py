# Use the Windows/OS certificate store so HTTPS works behind filtering proxies (verification stays on).
import truststore

truststore.inject_into_ssl()
