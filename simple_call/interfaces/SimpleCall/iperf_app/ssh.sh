#!/usr/bin/expect -f
spawn ssh username@10.44.131.181 "adb devices"
expect "assword:"
send "password\r"
interact
