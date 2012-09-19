          dsoc                                         
============================

'dsoc' - DSO _control - is a small command line utility to remotely control a Tekway/Hantek DSO
of the DSO5x02(B) series. It is written in python.

Prerequisite python libraries: pyusb, numpy and PIL (to save screenshots) 

The functionality is based on the reverse-engineered USB protocol which can be
seen at
[mikrocontroller.net](http://www.mikrocontroller.net/articles/Hantek_Protokoll)
(German) and [elinux.org](http://elinux.org/Das_Oszi_Protocol) (English).

It can be invoked as it can be seen below (from running ./dsoc --help). Each
sub-command has it's own help page which can be displayed by adding '--help'
to the command line.

    usage: dsoc [-h] [--show-comm] [--verbose]
		{ping,reset,cat,sh,screenshot,beep,samples,settings} ...

    Control a Tekway/HANTEK DSO through USB

    positional arguments:
      {ping,reset,cat,sh,screenshot,beep,samples,settings}
	ping                Test two-way communication with scope. Return code of
			    this command is zero when the scope is ready to accept
			    data.
	reset               Initialize/reset scope to power-on defaults.
	cat                 Get a file from the scope's internal linux file
			    system.
	sh                  Execute a command on the scope. WARNING: This command
			    is VERY DANGEROUS. It is easy to brick the scope and
			    things like 'r m -rf /' are NOT filtered. You have
			    been warned!
	screenshot          Take a screenshot on the scope and save it into a
			    file.
	beep                Turn on the buzzer on the scope.
	samples             Acquire sample data from the scope. Unless selected
			    otherwise, the output will be two-column ASCII data,
			    with the first column being time in second and the
			    second ADC values in volts.
	settings            Get a description of the current settings from the
			    scope as a list of keys and values.

    optional arguments:
      -h, --help            show this help message and exit
      --show-comm, -c       Show communication with DSO on stderr.
      --verbose, -v         Be verbose about the results of commands.


--
Onno Kortmann <onno@gmx.net>
