# Rhyme bot Task Scheduler registration
# Review the three XML files in this folder first, then run this script
# FROM AN ELEVATED PowerShell (schtasks /create with a logon trigger for a
# specific user requires admin). Tasks land under the \Rhyme\ folder in
# Task Scheduler.
#
# To register manually instead, run each schtasks line yourself.

schtasks /create /tn "\Rhyme\Rhyme-Swing"    /xml "D:\rhyme\scheduler\Rhyme-Swing.xml"
schtasks /create /tn "\Rhyme\Rhyme-Intraday" /xml "D:\rhyme\scheduler\Rhyme-Intraday.xml"
schtasks /create /tn "\Rhyme\Rhyme-Scalp30"  /xml "D:\rhyme\scheduler\Rhyme-Scalp30.xml"

# Verify:
schtasks /query /tn "\Rhyme\Rhyme-Swing" /v /fo LIST
schtasks /query /tn "\Rhyme\Rhyme-Intraday" /v /fo LIST
schtasks /query /tn "\Rhyme\Rhyme-Scalp30" /v /fo LIST

# To remove later:
#   schtasks /delete /tn "\Rhyme\Rhyme-Swing" /f
#   schtasks /delete /tn "\Rhyme\Rhyme-Intraday" /f
#   schtasks /delete /tn "\Rhyme\Rhyme-Scalp30" /f
