import os
if os.getenv("PORT"):
    from nexo_clinical.api import main
    main()
else:
    from nexo_clinical.cli import main
    main()
