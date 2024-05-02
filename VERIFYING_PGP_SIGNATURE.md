### Verifying GitHub Releases

You can verify the authenticity of the release artifacts using the `gpg` command line tool.

1) Download the desired release artifacts from the GitHub releases page. Make sure to download the corresponding PGP signature file (ending with `.sig`) as well.
For example, if you would like to verify your download of the wheel for version `1.2.3`, you should have the following files downloaded:
    ```
    openjd_cli-1.2.3-py3-none-any.whl
    openjd_cli-1.2.3-py3-none-any.whl.sig
    ```

2) Install the `gpg` command line tool. The installation process varies by operating system. Please refer to the GnuPG website for instructions: https://gnupg.org/download/

3) Save the following contents to a file called `openjobdescription-pgp.asc`:
    ```
    -----BEGIN PGP PUBLIC KEY BLOCK-----
    
    mQINBGXGjx0BEACdChrQ/nch2aYGJ4fxHNQwlPE42jeHECqTdlc1V/mug+7qN7Pc
    C4NQk4t68Y72WX/NG49gRfpAxPlSeNt18c3vJ9/sWTukmonWYGK0jQGnDWjuVgFT
    XtvJAAQBFilQXN8h779Th2lEuD4bQX+mGB7l60Xvh7vIehE3C4Srbp6KJXskPLPo
    dz/dx7a+GXRiyYCYbGX4JziXSjQZRc0tIaxLn/GDm7VnXpdHcUk3qJitree61oC8
    agtRHCH5s56E8wt8fXzyStElMkFIZsoLDlLp5lFqT81En9ho/+K6RLBkIj0mC8G7
    BafpHKlxkrIgNK3pWACL93GE6xihqwkZMCAeqloVvkOTdfAKDHuDSEHwKxHG3cZ1
    /e1YhtkPMVF+NMeoQavykUGVUT1bRoVNdk6bYsnbUjUI1A+JNf6MqvdRJyckZqEC
    ylkBekBp/SFpFHvQkRCpfVizm2GSrjdZKgXpm1ZlQJyMRVzc/XPbqdSWhz52r3IC
    eudwReHDc+6J5rs6tg3NbFfPVfCBMSqHlu1HRewWAllIp1+y6nfL4U3iEsUvZ1Y6
    IV3defHIP3kNPU14ZWf3G5rvJDZrIRnjoWhDcaVmivmB/cSdDzphL5FovSI8dsPm
    iU/JZGQb3EvZq+nl4pOiK32hETJ/fgCCzgUA3WqGeFNUNSI9KYZgBe6daQARAQAB
    tDRPcGVuIEpvYiBEZXNjcmlwdGlvbiA8b3BlbmpvYmRlc2NyaXB0aW9uQGFtYXpv
    bi5jb20+iQJXBBMBCABBFiEEvBcWYrv5OB7Tl2sZovDwWbzECYcFAmXGjx0DGy8E
    BQkDwmcABQsJCAcCAiICBhUKCQgLAgMWAgECHgcCF4AACgkQovDwWbzECYcSHRAA
    itPYx48xnJiT6tfnult9ZGivhcXhrMlvirVYOqEtRrt0l18sjr84K8mV71eqFwMx
    GS7e4iQP6guqW9biQfMA5/Id8ZjE7jNbF0LUGsY6Ktj+yOlAbTR+x5qr7Svb7oEs
    TMB/l9HBZ1WtIRzcUk9XYqzvYQr5TT997A63F28u32RchJ+5ECAz4g/p91aWxwVo
    HIfN10sGzttoukJCzC10CZAVscJB+nnoUbB/o3bPak6GUxBHpMgomb0K5g4Z4fXY
    4AZ9jKFoLgNcExdwteiUdSEnRorZ5Ny8sP84lwJziD3wuamVUsZ1C/KiQJBGTp5e
    LUY38J1oIwptw5fqjaAq2GQxEaIknWQ4fr3ZvNYUuGUt5FbHe5U5XF34gC8PK7v7
    bT/7sVdZZzKFScDLfH5N36M5FrXfTaXsVbfrRoa2j7U0kndyVEZyJsKVAQ8vgwbJ
    w/w2hKkyQLAg3l5yO5CHLGatsfSIzea4WoOAaroxiNtL9gzVXzqpw6qPEsH9hsws
    HsPEQWXHmDQvFTNUU14qic1Vc5fyxCBXIAGAPBd20b+219XznJ5uBKUgtvnqcItj
    nMYe6Btxh+pjrTA15X/p81z6sB7dkL1hPHfawLhCEzJbIPyyBTQYqY00/ap4Rj7t
    kzSiyzBejniFfAZ6eYBWsej7uXUsVndBF1ggZynPTeE=
    =iaEm
    -----END PGP PUBLIC KEY BLOCK-----
    ```

4) Import the OpenPGP key for Open Job Description by running the following command:

    ```
    gpg --import --armor openjobdescription-pgp.asc
    ```

5) Determine whether to trust the OpenPGP key. Some factors to consider when deciding whether or not to trust the above key are:

    - The internet connection you’ve used to obtain the GPG key from this website is secure
    - The device that you are accessing this website on is secure

    If you have decided to trust the OpenPGP key, then edit the key to trust with `gpg` like the following example:
    ```
    $ gpg --edit-key A2F0F059BCC40987
    gpg (GnuPG) 2.0.22; Copyright (C) 2013 Free Software Foundation, Inc.
    This is free software: you are free to change and redistribute it.
    There is NO WARRANTY, to the extent permitted by law.
    
    
    pub  4096R/BCC40987  created: 2024-02-09  expires: 2026-02-08  usage: SCEA
                         trust: unknown       validity: unknown
    [ unknown] (1). Open Job Description <openjobdescription@amazon.com>
    
    gpg> trust
    pub  4096R/BCC40987  created: 2024-02-09  expires: 2026-02-08  usage: SCEA
                         trust: unknown       validity: unknown
    [ unknown] (1). Open Job Description <openjobdescription@amazon.com>
    
    Please decide how far you trust this user to correctly verify other users' keys
    (by looking at passports, checking fingerprints from different sources, etc.)
    
      1 = I don't know or won't say
      2 = I do NOT trust
      3 = I trust marginally
      4 = I trust fully
      5 = I trust ultimately
      m = back to the main menu
    
    Your decision? 5
    Do you really want to set this key to ultimate trust? (y/N) y
    
    pub  4096R/BCC40987  created: 2024-02-09  expires: 2026-02-08  usage: SCEA
                         trust: ultimate      validity: unknown
    [ unknown] (1). Open Job Description <openjobdescription@amazon.com>
    Please note that the shown key validity is not necessarily correct
    unless you restart the program.
    
    gpg> quit
    ```

6) Verify the signature of the Open Job Description release via `gpg --verify`. The command for verifying the example files from step 1 would be:

    ```
    gpg --verify ./openjd_cli-1.2.3-py3-none-any.whl.sig ./openjd_cli-1.2.3-py3-none-any.whl
    ```