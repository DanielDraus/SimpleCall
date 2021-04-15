#!/usr/bin/expect -f
spawn ssh sranwro8@10.44.131.181 "adb devices"
expect "assword:"
send "wro8pass\r"
interact
